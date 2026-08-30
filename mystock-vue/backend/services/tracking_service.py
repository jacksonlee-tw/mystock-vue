"""追蹤與觀察名單的唯一寫入點（見 docs/15.追蹤個股清單優化/追蹤與觀察名單整合_規劃書.md §3.1 D3、§5.1）。

背景：系統原本有兩份獨立清單──「追蹤股票號碼」寫在 `.env` 的 `STOCK_CODES`/`US_STOCK_CODES`
（決定爬蟲每日抓什麼），「觀察名單」寫在 Postgres 的 `portfolio_watchlist`（記錄候選股與目標買進
價）。本模組把兩者合流成單一清單，Postgres 為**唯一**儲存──`is_crawl_enabled = TRUE` 的項目即
爬蟲抓取範圍。

**2026-08-30 起撤回 ADR-02**：原本 `.env` 是由本模組維護的鏡像，理由是
`config.get_target_stocks()` 有 8 處同步呼叫（爬蟲／回補／掃描／腳本），改成直讀 DB 會逼這些同步
程式背上 `asyncio.run()` 橋接負擔、且 JSON-only 部署會失去增刪追蹤清單的能力。使用者決議接受這個
取捨、正式停用 `.env` 鏡像：`config.get_target_stocks()` 改為直接查 Postgres（見該函式與
`repositories/portfolio_repository.py` 的背景連線池橋接說明），追蹤清單管理自此**一律要求 Postgres
可連線**，不再有 JSON-only 降級路徑；`scripts/migrate_tracking_list.py`／`scripts/sync_tracking_env.py`
（`.env` ↔ DB 遷移／對帳工具）與本檔原本的 `sync_env_mirror()`／`diff_env_vs_db()` 一併移除。

注意：這裡刻意**不**對 `config.get_data_source()` 做分支判斷——CLAUDE.md 規定該旗標只能在
`services/stock_service.load_stock_data()` 一處分支（它控制的是「K 線價格資料」讀取來源，跟本模組
管理的清單 metadata 是兩件事；`portfolio_*` 系列表本來就不受它影響，一律走 Postgres，同個人投資
記帳模組其餘功能）。

所有清單異動（新增／編輯／移除／暫停抓取／tag）都必須經過這裡；`api/v1/endpoints/watchlist.py`
與 `api/v1/endpoints/stocks.py` 的 `/tracked` 相容層一律呼叫本模組，不得直接操作
`PortfolioRepository`。DB 寫入失敗一律直接拋出例外（不再有 `.env` 退路），由呼叫端（API 層）轉成
錯誤回應。
"""
from __future__ import annotations

import logging
from typing import Optional

from db.session import get_async_session
from repositories.portfolio_repository import PortfolioRepository

logger = logging.getLogger("mystock-backend")


# ── 持股連動（規劃書 §12：ADR-08／ADR-09／ADR-11） ───────────────────────
async def upsert_from_holding(market: str, symbol: str, name: str) -> None:
    """新增交易時自動 upsert 進追蹤清單（ADR-08）：已存在則不動任何既有欄位（不覆寫使用者已
    設定的目標價／tag），不存在則新增純追蹤項目（`target_price=NULL`, `source='holding'`）。
    買賣皆呼叫同一函式，冪等，成本可忽略。呼叫端（transactions 端點／回填腳本）需自行 best-effort
    包一層例外，失敗只記警告、不擋交易寫入或回填流程。"""
    await upsert_item({
        "market": market, "symbol": symbol, "name": name,
        "is_crawl_enabled": True, "source": "holding",
    })


async def has_open_position(market: str, symbol: str) -> tuple[bool, float]:
    """查詢該 (market, symbol) 目前是否仍有非零持股（ADR-11：下架持股中股票要求確認）。
    複用既有 `portfolio_ledger.build_ledger()`，只餵入該檔股票自己的交易與股利，避免像
    `GET /portfolio/holdings` 那樣載入並計算全部持股。回傳 (has_position, shares)。"""
    from services.portfolio_ledger import Settings, build_ledger, to_float

    async with get_async_session() as session:
        repo = PortfolioRepository(session)
        transactions = await repo.list_transactions_for_symbol(market, symbol)
        if not transactions:
            return False, 0.0
        dividends = [d for d in await repo.list_dividends(market) if d["symbol"] == symbol]
        settings = Settings.from_row(await repo.get_settings())

    ledger = build_ledger(transactions, dividends, settings, quotes={})
    for p in ledger.positions:
        if p["market"] == market and p["symbol"] == symbol:
            return True, to_float(p["shares"])
    return False, 0.0


# ── DB 清單讀取 ────────────────────────────────────────────────────────
async def get_crawl_enabled_symbols(market: str) -> list[str]:
    """取得 DB 中目前啟用抓取的代號，供 API、畫面清單，以及所有已在事件迴圈內的 async 呼叫端使用
    （同步呼叫端改用 `config.get_target_stocks()`，見該函式說明）。"""
    async with get_async_session() as session:
        return await PortfolioRepository(session).list_crawl_enabled_symbols(market)


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


async def upsert_item(payload: dict) -> tuple[dict, bool]:
    """新增或部分更新一筆清單項目；回傳 (item, created)。

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

    return item, created


async def bulk_upsert_items(market: str, items: list[dict], source: str = "manual") -> list[dict]:
    """批次新增／更新清單項目（貼表格批次匯入用，見 `api/v1/endpoints/watchlist.py` 的
    `POST /watchlist/batch`）。逐筆呼叫 `upsert_item`——沿用同一寫入路徑與 ADR-05 部分更新語意
    （未帶到的欄位不覆寫既有值）、tag 整批覆寫行為——不直接操作 `PortfolioRepository`。單筆失敗
    （例如 symbol 為空、DB 例外）只記警告並記錄在回傳結果裡，不擋其他筆繼續匯入。

    回傳每筆的結果字典 `{"symbol", "ok", "created"?, "item"?, "error"?}`，供呼叫端（API 層）組
    created/updated/failed 統計與批次補抓（`ensure_data`）用的成功代號清單。"""
    results = []
    for raw in items:
        data = dict(raw)
        symbol = (data.get("symbol") or "").strip().upper()
        if not symbol:
            results.append({"symbol": raw.get("symbol") or "", "ok": False, "error": "股票代碼不可為空"})
            continue
        data["market"] = market
        data["symbol"] = symbol
        data["name"] = (data.get("name") or symbol).strip() or symbol
        data.setdefault("source", source)
        try:
            item, created = await upsert_item(data)
            results.append({"symbol": symbol, "ok": True, "created": created, "item": item})
        except Exception as exc:
            logger.warning("[追蹤清單] 批次匯入失敗 market=%s symbol=%s：%s", market, symbol, exc)
            results.append({"symbol": symbol, "ok": False, "error": str(exc)})
    return results


async def update_item(item_id: int, patch: dict) -> Optional[dict]:
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

    return item


async def set_crawl_enabled(item_id: int, enabled: bool) -> Optional[dict]:
    """暫停／恢復抓取（狀態模型見規劃書 §3.2）：is_crawl_enabled=false 不會刪除任何 metadata，
    只是把該代號從爬蟲抓取範圍（`config.get_target_stocks()` 的查詢結果）中剔除。"""
    return await update_item(item_id, {"is_crawl_enabled": enabled})


async def delete_item(item_id: int) -> Optional[str]:
    """移除清單項目；回傳 market，找不到回傳 None。
    不動任何已抓到的歷史價格資料（daily_stock_data / data/{tw,us}/<symbol>.json 不刪）。"""
    async with get_async_session() as session:
        repo = PortfolioRepository(session)
        row = await repo.get_watchlist_by_id(item_id)
        if not row:
            return None
        await repo.delete_watchlist(item_id)
        await session.commit()

    return row["market"]


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
    """相容層批次新增：codes 已由呼叫端 trim／去重。upsert 進 DB（維持既有『純追蹤』新增語意，
    不帶 target_price/note）。回傳 {"added": [...], "already_tracked": [...]}。
    Postgres 連線失敗時直接拋出例外（2026-08-30 起不再有退回 .env 的相容路徑，見本檔開頭說明），
    由呼叫端（API 層）轉成錯誤回應。"""
    current = set(await get_crawl_enabled_symbols(market))
    already = [c for c in codes if c in current]
    new_codes = [c for c in codes if c not in current]

    if new_codes:
        async with get_async_session() as session:
            repo = PortfolioRepository(session)
            for code in new_codes:
                await repo.upsert_watchlist({
                    "market": market, "symbol": code, "name": code,
                    "is_crawl_enabled": True, "source": source,
                })
            await session.commit()

    return {"added": new_codes, "already_tracked": already}


async def remove_code(code: str, market: str) -> bool:
    """相容層移除：在 DB 中尋找並刪除。回傳是否有找到並移除。Postgres 連線失敗時直接拋出例外
    （見 add_codes() 說明）。"""
    async with get_async_session() as session:
        repo = PortfolioRepository(session)
        row = await repo.get_watchlist_by_symbol(market, code)
        if not row:
            return False
        await repo.delete_watchlist(row["id"])
        await session.commit()
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
