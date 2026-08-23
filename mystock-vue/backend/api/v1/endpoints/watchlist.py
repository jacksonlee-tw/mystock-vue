"""追蹤與觀察名單（原「潛力股觀察名單」，設計文件 §五；整合擴充見
docs/14.追蹤個股清單優化/追蹤與觀察名單整合_規劃書.md §5.2）。

系統唯一的個股清單頁 API：一檔股票加入後即納入每日爬蟲抓取範圍（is_crawl_enabled），可選填目標
買進價（觀察標的，算距目標／到價提醒）與追蹤原因，並可掛多個自訂 tag。所有寫入一律經
services/tracking_service.py（唯一寫入點），不得直接呼叫 PortfolioRepository 或
config.save_target_stocks()。到價推播（串接整合訊息通知平台）尚未串接，目前僅頁面顯示距目標價。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from db.session import get_db
from repositories.portfolio_repository import PortfolioRepository
from services import tracking_service
from services.portfolio_ledger import D, Settings, to_float

router = APIRouter(prefix="/api/v1/watchlist", tags=["Portfolio - Watchlist"])


class WatchlistIn(BaseModel):
    market: str
    symbol: str
    name: Optional[str] = None
    target_price: Optional[float] = None
    note: Optional[str] = None
    tags: Optional[List[str]] = None
    source: Optional[str] = "manual"
    is_crawl_enabled: Optional[bool] = None


class WatchlistUpdate(BaseModel):
    target_price: Optional[float] = None
    note: Optional[str] = None
    name: Optional[str] = None
    tags: Optional[List[str]] = None
    is_crawl_enabled: Optional[bool] = None


class CrawlToggleIn(BaseModel):
    enabled: bool


class TagIn(BaseModel):
    name: str
    color: str = "slate"


class TagUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None


async def _quotes_for(rows: list[dict]) -> dict[tuple[str, str], float]:
    from api.v1.endpoints.portfolio import _fetch_quotes  # 重用既有批次報價邏輯，不重複實作

    pairs = [(r["market"], r["symbol"]) for r in rows]
    quotes = await _fetch_quotes(pairs)
    return {k: to_float(v) for k, v in quotes.items()}


def _watch_out(row: dict, price: Optional[float], near_target_pct: float) -> dict:
    target_price = to_float(row["target_price"]) if row.get("target_price") is not None else None
    gap_pct = ((price / target_price - 1) * 100) if (price is not None and target_price) else None
    out = {
        "id": row["id"], "market": row["market"], "symbol": row["symbol"], "name": row["name"],
        "added_date": row["added_date"].isoformat() if row.get("added_date") else None,
        "target_price": target_price, "note": row.get("note"), "tags": row.get("tags") or [],
        "is_crawl_enabled": row.get("is_crawl_enabled", True), "source": row.get("source"),
        "price": price, "gap_pct": gap_pct,
        "is_near_target": (gap_pct is not None and abs(gap_pct) <= near_target_pct),
        "is_reached": (gap_pct is not None and gap_pct <= 0),
    }
    if "coverage" in row:
        out["coverage"] = row["coverage"]
    return out


def _parse_tag_ids(tags: Optional[str]) -> Optional[list[int]]:
    if not tags:
        return None
    ids = [int(t) for t in tags.split(",") if t.strip().isdigit()]
    return ids or None


@router.get("", summary="查詢追蹤與觀察名單（含目前股價與距目標價）")
async def list_watchlist(
    market: Optional[str] = Query(None),
    tags: Optional[str] = Query(None, description="tag id，逗號分隔，多選為 AND 語意"),
    q: Optional[str] = Query(None, description="代號或名稱關鍵字"),
    has_target: Optional[bool] = Query(None, description="true=只看已設目標價，false=只看純追蹤"),
    crawl_only: Optional[bool] = Query(None, description="true=只看目前納入抓取範圍的項目"),
    with_coverage: bool = Query(False, description="是否附帶資料涵蓋範圍（起訖日期／缺漏天數）"),
    db=Depends(get_db),
):
    rows = await tracking_service.list_items(
        market, tag_ids=_parse_tag_ids(tags), keyword=q, has_target=has_target,
        crawl_only=crawl_only, with_coverage=with_coverage,
    )
    settings = Settings.from_row(await PortfolioRepository(db).get_settings())
    quotes = await _quotes_for(rows)
    data = [_watch_out(r, quotes.get((r["market"], r["symbol"])), to_float(settings.near_target_pct)) for r in rows]
    return {"success": True, "data": data}


@router.post("", summary="加入追蹤／觀察（同代碼同市場已存在則部分更新，不覆寫未帶到的欄位）")
async def add_watchlist(payload: WatchlistIn, background_tasks: BackgroundTasks, db=Depends(get_db)):
    if payload.market not in ("tw", "us"):
        raise HTTPException(400, "market 必須為 tw 或 us")
    if payload.target_price is not None and payload.target_price <= 0:
        raise HTTPException(400, "目標買進價若填寫，必須大於 0")

    symbol = payload.symbol.strip().upper()
    data = payload.model_dump(exclude_unset=True, exclude={"market", "symbol"})
    data["market"] = payload.market
    data["symbol"] = symbol
    data["name"] = (data.get("name") or symbol).strip() or symbol
    if "target_price" in data and data["target_price"] is not None:
        data["target_price"] = D(data["target_price"])

    item, created, mirror_warning = await tracking_service.upsert_item(data)
    # 加入後自動補抓（ADR-06）：沒有歷史資料的才會觸發，已有資料或已有抓取任務執行中時是 no-op
    fetch_triggered = await tracking_service.ensure_data([symbol], payload.market, background_tasks)
    settings = Settings.from_row(await PortfolioRepository(db).get_settings())
    quotes = await _quotes_for([item])
    return {
        "success": True,
        "data": _watch_out(item, quotes.get((item["market"], item["symbol"])), to_float(settings.near_target_pct)),
        "message": "已加入追蹤清單" if created else "該股已在清單中，已更新設定",
        "mirror_warning": mirror_warning,
        "fetch_triggered": fetch_triggered,
    }


@router.put("/{watch_id}", summary="編輯清單項目（目標價／追蹤原因／名稱／tag／是否納入抓取）")
async def update_watchlist(watch_id: int, payload: WatchlistUpdate, background_tasks: BackgroundTasks, db=Depends(get_db)):
    if payload.target_price is not None and payload.target_price <= 0:
        raise HTTPException(400, "目標買進價若填寫，必須大於 0")

    patch = payload.model_dump(exclude_unset=True)
    if "target_price" in patch and patch["target_price"] is not None:
        patch["target_price"] = D(patch["target_price"])
    if patch.get("name") is not None and not patch["name"].strip():
        patch.pop("name")

    result = await tracking_service.update_item(watch_id, patch)
    if result is None:
        raise HTTPException(404, "找不到清單項目")
    item, mirror_warning = result

    # 加入後自動補抓（ADR-06）：只在目前是「納入抓取」狀態時才檢查，暫停抓取的項目編輯備註/tag
    # 不該連帶觸發抓取；涵蓋前端編輯彈窗把「恢復抓取」跟其他欄位一起送出（走 PUT 而非 PATCH /crawl）的情況。
    fetch_triggered: list[str] = []
    if item["is_crawl_enabled"]:
        fetch_triggered = await tracking_service.ensure_data([item["symbol"]], item["market"], background_tasks)

    settings = Settings.from_row(await PortfolioRepository(db).get_settings())
    quotes = await _quotes_for([item])
    return {
        "success": True,
        "fetch_triggered": fetch_triggered,
        "data": _watch_out(item, quotes.get((item["market"], item["symbol"])), to_float(settings.near_target_pct)),
        "message": "已更新清單項目",
        "mirror_warning": mirror_warning,
    }


@router.patch("/{watch_id}/crawl", summary="暫停／恢復抓取（不刪除任何 metadata）")
async def toggle_crawl(watch_id: int, payload: CrawlToggleIn, background_tasks: BackgroundTasks):
    result = await tracking_service.set_crawl_enabled(watch_id, payload.enabled)
    if result is None:
        raise HTTPException(404, "找不到清單項目")
    item, mirror_warning = result

    fetch_triggered: list[str] = []
    if payload.enabled:
        # 恢復抓取時比照新增：沒有歷史資料的話順便補抓，不必等下次排程或使用者手動重抓
        fetch_triggered = await tracking_service.ensure_data([item["symbol"]], item["market"], background_tasks)

    return {
        "success": True,
        "message": "已恢復抓取" if payload.enabled else "已暫停抓取（設定仍保留）",
        "data": {"id": item["id"], "is_crawl_enabled": item["is_crawl_enabled"]},
        "mirror_warning": mirror_warning,
        "fetch_triggered": fetch_triggered,
    }


@router.delete("/{watch_id}", summary="移除清單項目（不影響任何交易紀錄或已抓取的歷史資料）")
async def delete_watchlist(watch_id: int):
    result = await tracking_service.delete_item(watch_id)
    if result is None:
        raise HTTPException(404, "找不到清單項目")
    _market, mirror_warning = result
    return {"success": True, "message": "已從清單移除", "mirror_warning": mirror_warning}


# ── 自訂標籤 ──────────────────────────────────────────────────────────
@router.get("/tags", summary="取得所有自訂標籤（含引用次數）")
async def list_tags():
    return {"success": True, "data": await tracking_service.list_tags()}


@router.post("/tags", summary="新增自訂標籤")
async def create_tag(payload: TagIn):
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "標籤名稱不可為空")
    try:
        tag = await tracking_service.create_tag(name, payload.color)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"success": True, "data": tag, "message": "已新增標籤"}


@router.put("/tags/{tag_id}", summary="編輯標籤（更名／改色一次對所有引用生效）")
async def update_tag(tag_id: int, payload: TagUpdate):
    patch = payload.model_dump(exclude_unset=True)
    if patch.get("name") is not None:
        patch["name"] = patch["name"].strip()
        if not patch["name"]:
            raise HTTPException(400, "標籤名稱不可為空")
    try:
        tag = await tracking_service.update_tag(tag_id, patch)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if tag is None:
        raise HTTPException(404, "找不到標籤")
    return {"success": True, "data": tag, "message": "已更新標籤"}


@router.delete("/tags/{tag_id}", summary="刪除標籤（只移除關聯，不影響清單項目本身）")
async def delete_tag(tag_id: int):
    ok = await tracking_service.delete_tag(tag_id)
    if not ok:
        raise HTTPException(404, "找不到標籤")
    return {"success": True, "message": "已刪除標籤"}
