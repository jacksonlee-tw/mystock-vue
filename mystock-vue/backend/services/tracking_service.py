"""追蹤與觀察名單的唯一寫入點（見 docs/14.追蹤個股清單優化/追蹤與觀察名單整合_規劃書.md §3.1 D3、§5.1）。

背景：系統原本有兩份獨立清單──「追蹤股票號碼」寫在 `.env` 的 `STOCK_CODES`/`US_STOCK_CODES`
（決定爬蟲每日抓什麼），「觀察名單」寫在 Postgres 的 `portfolio_watchlist`（記錄候選股與目標買進
價）。本模組把兩者合流成單一清單：**Postgres 為 metadata 主儲存，`.env` 降為由本模組維護的鏡像**
（ADR-02）──理由是 `config.get_target_stocks()` 目前有 8 處同步呼叫（爬蟲／回補／掃描／腳本），
若改成直讀 DB 會逼這些同步程式全部背上 `asyncio.run()` 橋接負擔。

注意：這裡刻意**不**對 `config.get_data_source()` 做分支判斷——CLAUDE.md 規定該旗標只能在
`services/stock_service.load_stock_data()` 一處分支（它控制的是「K 線價格資料」讀取來源，跟本模組
管理的清單 metadata 是兩件事；`portfolio_*` 系列表本來就不受它影響，一律走 Postgres，同個人投資
記帳模組其餘功能）。`/api/v1/stocks/tracked` 相容層的批次新增／移除是唯二會在「Postgres 連線失敗」
時退回直接操作 `.env` 的地方，比照 `markets/tw.py` `validate_symbols()` 的既有先例（try DB、失敗記
警告、不阻斷流程），藉此維持既有「JSON-only 部署也能增刪追蹤清單」的能力（規劃書 §2.3 相容點 #5）。

所有清單異動（新增／編輯／移除／暫停抓取／tag）都必須經過這裡；`api/v1/endpoints/watchlist.py`
與 `api/v1/endpoints/stocks.py` 的 `/tracked` 相容層一律呼叫本模組，不得直接操作
`PortfolioRepository` 或 `config.save_target_stocks()`。

鏡像寫入的時機是「DB commit 成功之後」，且是 best-effort（比照 `db/dual_write.py` 的第二寫入慣例）：
寫入 `.env` 失敗只記警告、回傳 `mirror_warning` 供前端提示，不讓整次清單操作失敗。
"""
from __future__ import annotations

import logging
from typing import Optional

from config import get_target_stocks, save_target_stocks
from db.session import get_async_session
from repositories.portfolio_repository import PortfolioRepository

logger = logging.getLogger("mystock-backend")


# ── .env 鏡像 ────────────────────────────────────────────────────────────
async def sync_env_mirror(market: str) -> None:
    """依 DB 目前 is_crawl_enabled=TRUE 的清單重寫 .env 鏡像。"""
    async with get_async_session() as session:
        symbols = await PortfolioRepository(session).list_crawl_enabled_symbols(market)
    save_target_stocks(symbols, market=market)


async def _try_sync_mirror(market: str) -> Optional[str]:
    """包一層例外處理：鏡像寫入失敗不讓呼叫端的清單操作失敗，只回傳警告文字。"""
    try:
        await sync_env_mirror(market)
        return None
    except Exception as exc:
        logger.warning("[追蹤清單] 重寫 .env 鏡像失敗（market=%s）：%s", market, exc)
        return "已寫入資料庫，但同步爬蟲設定檔（.env）失敗，請確認 backend/.env 是否可寫入"


async def diff_env_vs_db(market: str) -> dict:
    """比較 .env 與 DB 的追蹤代碼是否一致，供啟動對帳與 scripts/sync_tracking_env.py 共用。
    只回傳差異，不做任何修改（§4.3：不自動修改，避免啟動時偷改使用者設定）。DB 查詢失敗
    （例如 Postgres 未部署）時略過本次對帳，回傳 checked=False，不當成「有差異」誤報。"""
    env_symbols = set(get_target_stocks(market=market))
    try:
        async with get_async_session() as session:
            db_symbols = set(await PortfolioRepository(session).list_crawl_enabled_symbols(market))
    except Exception as exc:
        logger.warning("[追蹤清單] 對帳查詢資料庫失敗（market=%s），略過本次對帳：%s", market, exc)
        return {"market": market, "only_in_env": [], "only_in_db": [], "in_sync": True, "checked": False}
    only_in_env = sorted(env_symbols - db_symbols)
    only_in_db = sorted(db_symbols - env_symbols)
    return {
        "market": market, "only_in_env": only_in_env, "only_in_db": only_in_db,
        "in_sync": not only_in_env and not only_in_db, "checked": True,
    }


# ── 清單查詢／增修（/api/v1/watchlist 主要業務邏輯） ─────────────────────
async def _attach_coverage(items: list[dict]) -> list[dict]:
    """批次補上每筆項目的資料涵蓋範圍（見 StockRepository.get_coverage_summary）。"""
    from repositories.stock_repository import StockRepository

    by_market: dict[str, list[str]] = {}
    for item in items:
        by_market.setdefault(item["market"], []).append(item["symbol"])

    stock_repo = StockRepository()
    coverage_by_market = {
        m: await stock_repo.get_coverage_summary(symbols, m) for m, symbols in by_market.items()
    }
    for item in items:
        item["coverage"] = coverage_by_market.get(item["market"], {}).get(item["symbol"])
    return items


async def list_items(
    market: Optional[str] = None, *, tag_ids: Optional[list[int]] = None,
    keyword: Optional[str] = None, has_target: Optional[bool] = None,
    crawl_only: Optional[bool] = None, with_coverage: bool = False,
) -> list[dict]:
    async with get_async_session() as session:
        items = await PortfolioRepository(session).list_watchlist(
            market, tag_ids=tag_ids, keyword=keyword, has_target=has_target, crawl_only=crawl_only
        )
    if with_coverage and items:
        items = await _attach_coverage(items)
    return items


async def get_item(item_id: int) -> Optional[dict]:
    async with get_async_session() as session:
        return await PortfolioRepository(session).get_watchlist_by_id(item_id)


async def upsert_item(payload: dict) -> tuple[dict, bool, Optional[str]]:
    """新增或部分更新一筆清單項目；回傳 (item, created, mirror_warning)。

    `payload` 只放實際要寫入／更新的欄位，未帶到的欄位（例如一鍵加入追蹤時不帶 target_price）
    完全不動既有值（ADR-05：避免覆寫使用者已設好的目標價／原因）。`tags`（可選，`list[str]`）
    帶入時整批覆寫該項目的 tag；不帶（`None`）則不動既有 tag。"""
    data = dict(payload)
    tag_names = data.pop("tags", None)

    async with get_async_session() as session:
        repo = PortfolioRepository(session)
        item, created = await repo.upsert_watchlist(data)
        if tag_names is not None:
            tags = await repo.get_or_create_tags(tag_names)
            await repo.set_watchlist_tags(item["id"], [t.id for t in tags])
            item = await repo.get_watchlist_by_id(item["id"])
        await session.commit()

    mirror_warning = await _try_sync_mirror(item["market"])
    return item, created, mirror_warning


async def update_item(item_id: int, patch: dict) -> Optional[tuple[dict, Optional[str]]]:
    """部分更新（同 upsert_item 的 ADR-05 語意）。找不到回傳 None。"""
    data = dict(patch)
    tag_names = data.pop("tags", None)

    async with get_async_session() as session:
        repo = PortfolioRepository(session)
        item = await repo.update_watchlist(item_id, data) if data else await repo.get_watchlist_by_id(item_id)
        if item is None:
            return None
        if tag_names is not None:
            tags = await repo.get_or_create_tags(tag_names)
            await repo.set_watchlist_tags(item_id, [t.id for t in tags])
            item = await repo.get_watchlist_by_id(item_id)
        await session.commit()

    mirror_warning = await _try_sync_mirror(item["market"])
    return item, mirror_warning


async def set_crawl_enabled(item_id: int, enabled: bool) -> Optional[tuple[dict, Optional[str]]]:
    """暫停／恢復抓取（狀態模型見規劃書 §3.2）：is_crawl_enabled=false 不會刪除任何 metadata，
    只是把該代號從 .env 鏡像中剔除。"""
    return await update_item(item_id, {"is_crawl_enabled": enabled})


async def delete_item(item_id: int) -> Optional[tuple[str, Optional[str]]]:
    """移除清單項目；回傳 (market, mirror_warning)，找不到回傳 None。
    不動任何已抓到的歷史價格資料（daily_stock_data / data/{tw,us}/<symbol>.json 不刪）。"""
    async with get_async_session() as session:
        repo = PortfolioRepository(session)
        row = await repo.get_watchlist_by_id(item_id)
        if not row:
            return None
        await repo.delete_watchlist(item_id)
        await session.commit()

    mirror_warning = await _try_sync_mirror(row["market"])
    return row["market"], mirror_warning


# ── 自訂標籤 CRUD ───────────────────────────────────────────────────────
async def list_tags() -> list[dict]:
    async with get_async_session() as session:
        return await PortfolioRepository(session).list_tags()


async def create_tag(name: str, color: str = "slate") -> dict:
    """`ValueError`（重複名稱）交由呼叫端（API 層）轉成 400，這裡不吞。"""
    async with get_async_session() as session:
        repo = PortfolioRepository(session)
        tag = await repo.create_tag(name, color)
        await session.commit()
        return tag


async def update_tag(tag_id: int, patch: dict) -> Optional[dict]:
    async with get_async_session() as session:
        repo = PortfolioRepository(session)
        tag = await repo.update_tag(tag_id, patch)
        if tag is not None:
            await session.commit()
        return tag


async def delete_tag(tag_id: int) -> bool:
    async with get_async_session() as session:
        repo = PortfolioRepository(session)
        ok = await repo.delete_tag(tag_id)
        if ok:
            await session.commit()
        return ok


# ── /api/v1/stocks/tracked 相容層（見 api/v1/endpoints/stocks.py） ──────
async def add_codes(codes: list[str], market: str, source: str = "manual") -> dict:
    """相容層批次新增：codes 已由呼叫端 trim／去重。優先 upsert 進 DB（維持既有『純追蹤』新增
    語意，不帶 target_price/note）；Postgres 連線失敗時退回直接寫 .env，維持既有「JSON-only
    部署也能增刪追蹤清單」的能力。回傳 {"added": [...], "already_tracked": [...]}。"""
    current = set(get_target_stocks(market=market))
    already = [c for c in codes if c in current]
    new_codes = [c for c in codes if c not in current]

    if new_codes:
        try:
            async with get_async_session() as session:
                repo = PortfolioRepository(session)
                for code in new_codes:
                    await repo.upsert_watchlist({
                        "market": market, "symbol": code, "name": code,
                        "is_crawl_enabled": True, "source": source,
                    })
                await session.commit()
            await _try_sync_mirror(market)
        except Exception as exc:
            logger.warning("[追蹤清單] 寫入資料庫失敗，退回直接寫入 .env（market=%s）：%s", market, exc)
            save_target_stocks(list(current) + new_codes, market=market)

    return {"added": new_codes, "already_tracked": already}


async def remove_code(code: str, market: str) -> bool:
    """相容層移除：優先在 DB 中尋找並刪除；DB 不可用、或該代碼只存在於 .env（尚未遷移進 DB）
    時，改直接由 .env 移除。回傳是否有找到並移除。"""
    removed_from_db = False
    try:
        async with get_async_session() as session:
            repo = PortfolioRepository(session)
            row = await repo.get_watchlist_by_symbol(market, code)
            if row:
                await repo.delete_watchlist(row["id"])
                await session.commit()
                removed_from_db = True
    except Exception as exc:
        logger.warning("[追蹤清單] 查詢/刪除資料庫失敗，退回直接操作 .env（market=%s）：%s", market, exc)

    if removed_from_db:
        await _try_sync_mirror(market)
        return True

    current = get_target_stocks(market=market)
    if code not in current:
        return False
    save_target_stocks([c for c in current if c != code], market=market)
    return True


# ── 加入後自動補抓（ADR-06：搬到後端，所有入口一致） ─────────────────────
async def ensure_data(codes: list[str], market: str, background_tasks) -> list[str]:
    """檢查 codes 是否已有歷史資料，沒有的批次觸發背景抓取。

    取代舊版只寫在 `StockManagement.vue` 前端的判斷邏輯（逐檔打 `getChartData` 檢查、沒有的
    才 `triggerFetch`）：搬到這裡後，`/api/v1/watchlist`（單筆加入）與 `/api/v1/stocks/tracked`
    （批次加入）兩個入口都會自動觸發，解決規劃書 P2「加入觀察名單不會抓資料」的問題，不必每個
    前端頁面各自重寫一次判斷。

    `background_tasks` 是呼叫端（API 層）注入的 FastAPI `BackgroundTasks`：`run_fetch_process`／
    `run_us_fetch_process` 是同步、阻塞的爬蟲函式（見 services/fetcher.py），不能在這個 async
    函式裡直接呼叫，否則會卡住事件迴圈；必須丟給 `BackgroundTasks`，比照 `api/v1/endpoints/fetch.py`
    既有的觸發方式。

    回傳實際觸發抓取的代碼清單（供呼叫端組訊息用）；已有其他抓取任務執行中時整批略過、不重複
    觸發（沿用 `services/fetcher.py` 的 `fetch_status` 全域互斥旗標），呼叫端下次加入時仍會再檢查。

    比照本模組其餘 best-effort 邏輯：判斷本身查詢失敗（例如 Postgres 未部署）不會讓呼叫端的
    加入操作跟著失敗，只記警告並回傳空清單（視同「這次沒有補抓」，不阻斷主流程）。
    """
    if not codes:
        return []

    try:
        from repositories.stock_repository import StockRepository

        coverage = await StockRepository().get_coverage_summary(codes, market)
    except Exception as exc:
        logger.warning("[追蹤清單] 補抓判斷查詢資料庫失敗，略過本次自動補抓（market=%s）：%s", market, exc)
        return []

    need_fetch = [c for c in codes if not coverage.get(c, {}).get("count")]
    if not need_fetch:
        return []

    from services.fetcher import fetch_status

    if fetch_status.get_snapshot()["is_running"]:
        logger.info("[追蹤清單] 補抓略過（已有抓取任務執行中）：%s", need_fetch)
        return []

    from config import get_months_range

    months = get_months_range()
    if market == "us":
        from services.us_fetcher import run_us_fetch_process

        background_tasks.add_task(run_us_fetch_process, target_stocks=need_fetch, months=months, mode="incremental")
    else:
        from services.fetcher import run_fetch_process

        background_tasks.add_task(run_fetch_process, target_stocks=need_fetch, months=months, mode="incremental")
    return need_fetch
