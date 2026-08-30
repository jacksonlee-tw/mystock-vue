"""
api/v1/endpoints/industry_chains.py
產業鏈知識圖譜 API（見 docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §7）。

規格書 §7 的 5 個端點本檔全部到齊：`spillover-radar` 這一批補上（industry_chain/spillover.py
已提供 BFS／濾網／點火偵測），`{chain_id}/graph` 也一併改用 `spillover.compute_node_states()`
填入真正的節點狀態，取代上一批的 `state: null` 佔位。

`GET/PUT /config` 是規格書之外新增的「管理產業鏈」維護對話框端點（前端不用再手動編輯
industry_chain_config/industry_chains.yaml）：純檔案操作，不查 DB，也不受 _check_enabled()
限制，理由見各自的 docstring。

比照 ai_analysis.py 的既有慣例：`{"success": bool, "data"/"error": ...}` 回應封套，例外一律
轉為 industry_chain/errors.py 的型別，交給 main.py 的例外處理器轉成 HTTP 回應（不在端點內
自己 try/except 轉 JSONResponse）。
"""
from __future__ import annotations
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from industry_chain import config as ic_config
from industry_chain.errors import IndustryChainDisabledException, IndustryChainNotFoundException
from repositories.industry_chain_repository import IndustryChainRepository
from repositories.stock_repository import StockRepository

logger = logging.getLogger("mystock-backend")

router = APIRouter(prefix="/api/v1/industry-chains", tags=["Industry Chains"])


class ExtractTriggerRequest(BaseModel):
    chain_id: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class ChainConfigItem(BaseModel):
    chain_id: str
    name: str
    downstream_leaders: list[str] = []
    lead_lag_window_days: Optional[list[int]] = None
    extraction_hint: str = ""
    note: str = ""


class SaveChainConfigRequest(BaseModel):
    items: list[ChainConfigItem]


def _check_enabled() -> None:
    if not ic_config.is_enabled():
        raise IndustryChainDisabledException("產業鏈知識圖譜功能未啟用")


@router.get("", summary="列出所有產業鏈（YAML 骨架 + 邊數量統計）")
async def list_chains():
    _check_enabled()
    from db.session import get_async_session

    chains = ic_config.load_chains()
    async with get_async_session() as session:
        repo = IndustryChainRepository(session)
        items = []
        for c in chains:
            edges = await repo.list_edges(chain_id=c.chain_id)
            items.append({
                "chain_id": c.chain_id,
                "name": c.name,
                "downstream_leaders": c.downstream_leaders,
                "edge_count": len(edges),
                "verified_edge_count": sum(1 for e in edges if e["is_verified"]),
            })
    return {"success": True, "data": {"items": items}}


@router.get("/config", summary="產業鏈骨架設定（維護對話框用，純讀 YAML，不查 DB、不受總開關限制）")
async def get_chains_config():
    # 刻意不呼叫 _check_enabled()：骨架設定本身是純檔案操作，應該在打開 INDUSTRY_CHAIN_ENABLED
    # 之前就能編輯（先把鏈設好，再開關），也不應該因為功能關閉就連檔案內容都看不到。
    return {"success": True, "data": {"items": ic_config.load_chain_config_items()}}


@router.put("/config", summary="整份覆寫產業鏈骨架設定（維護對話框「儲存」，新增/編輯/刪除皆走此端點）")
async def save_chains_config(req: SaveChainConfigRequest):
    cleaned = ic_config.validate_chain_config_items([item.model_dump() for item in req.items])
    ic_config.save_chain_config(cleaned)
    return {"success": True, "data": {"items": cleaned}}


@router.get("/{chain_id}/graph", summary="該鏈的節點與邊（Node-Edge JSON，供力導向圖使用）")
async def get_chain_graph(chain_id: str):
    _check_enabled()
    from db.session import get_async_session

    chain = ic_config.get_chain(chain_id)
    if chain is None:
        raise IndustryChainNotFoundException(f"找不到產業鏈：{chain_id}")

    from industry_chain import spillover
    from services.stock_service import get_latest_quote

    async with get_async_session() as session:
        repo = IndustryChainRepository(session)
        edges = await repo.list_edges(chain_id=chain_id)

        min_tier: dict[str, int] = {}
        node_symbols: set[str] = set()
        market_by_symbol: dict[str, str] = {}
        for e in edges:
            node_symbols.add(e["upstream_symbol"])
            node_symbols.add(e["downstream_symbol"])
            market_by_symbol[e["upstream_symbol"]] = e["upstream_market"]
            market_by_symbol[e["downstream_symbol"]] = e["downstream_market"]
            up = e["upstream_symbol"]
            min_tier[up] = min(min_tier.get(up, e["relation_tier"]), e["relation_tier"])
        node_symbols.update(chain.downstream_leaders)

        # 名稱查詢依節點各自所屬市場分組。早期版本一律以 "tw" 查詢，美股節點（如 LITE／COHR）
        # 因此查無名稱，前端只好把代號顯示兩次；`market` 同時也回傳給前端，讓「加入追蹤觀察
        # 清單」知道該用哪個市場送出（watchlist 的批次端點是一次一個市場）
        symbols_by_market: dict[str, list[str]] = {}
        for symbol in node_symbols:
            symbols_by_market.setdefault(market_by_symbol.get(symbol, "tw"), []).append(symbol)

        stock_repo = StockRepository()
        names: dict[str, str] = {}
        for market, syms in symbols_by_market.items():
            for row in await stock_repo.get_symbols(sorted(syms), market):
                names[row["symbol"]] = row["name"]

        # 最近一筆有效收盤價（含日期）。併發取得，比照 portfolio.py 的 _fetch_quotes() 既有作法；
        # 日期逐節點回傳而非整張表共用一個——台股與美股最後交易日本來就不同步，共用一個日期會
        # 讓其中一邊的價格被標上錯誤的日期。get_latest_quote() 會跳過收盤價 0 的補值列，
        # 查無資料回 None，前端顯示「待報價」
        quote_symbols = sorted(node_symbols)
        quote_results = await asyncio.gather(*(
            get_latest_quote(symbol, market_by_symbol.get(symbol, "tw")) for symbol in quote_symbols
        ))
        quotes = {q["symbol"]: q for q in quote_results if q}

        radar_items = await spillover.build_radar(chain_id, session)
        states = await spillover.compute_node_states(chain, edges, radar_items)

        nodes = []
        for symbol in sorted(node_symbols):
            if symbol in chain.downstream_leaders:
                role = "downstream"
            else:
                role = "tier1" if min_tier.get(symbol, 2) == 1 else "tier2"
            nodes.append({
                "symbol": symbol,
                "name": names.get(symbol, symbol),
                "market": market_by_symbol.get(symbol, "tw"),
                "role": role,
                "state": states.get(symbol, "dormant"),
                "close": quotes.get(symbol, {}).get("close"),
                "quote_date": quotes.get(symbol, {}).get("date"),
                # 該節點作為上游時供應的品項，供前端「加入追蹤觀察清單」帶入追蹤原因
                "component_type": next(
                    (e["component_type"] for e in edges if e["upstream_symbol"] == symbol and e["component_type"]),
                    None,
                ),
            })

        edge_items = [
            {
                "id": e["id"], "upstream_symbol": e["upstream_symbol"], "downstream_symbol": e["downstream_symbol"],
                "relation_tier": e["relation_tier"], "component_type": e["component_type"],
                "source": e["source"], "is_verified": e["is_verified"], "is_active": e["is_active"],
                "extra_data": e.get("extra_data"),
            }
            for e in edges
        ]

    return {
        "success": True,
        "data": {"chain_id": chain.chain_id, "name": chain.name, "nodes": nodes, "edges": edge_items},
    }


@router.get("/{symbol}/lead-lag", summary="該標的與其上下游的 CCF 時差曲線")
async def get_symbol_lead_lag(symbol: str):
    _check_enabled()
    from db.session import get_async_session

    async with get_async_session() as session:
        repo = IndustryChainRepository(session)
        all_edges = await repo.list_edges()
        related = [e for e in all_edges if e["upstream_symbol"] == symbol or e["downstream_symbol"] == symbol]

        items = []
        for e in related:
            cache_rows = await repo.list_lead_lag_for_edge(e["id"])
            latest = cache_rows[0] if cache_rows else None  # list_lead_lag_for_edge 已依 window_end DESC 排序
            items.append({
                "edge_id": e["id"], "chain_id": e["chain_id"],
                "upstream_symbol": e["upstream_symbol"], "downstream_symbol": e["downstream_symbol"],
                "component_type": e["component_type"], "relation_tier": e["relation_tier"],
                "peak_lag_days": latest["peak_lag_days"] if latest else None,
                "correlation_coefficient": float(latest["correlation_coefficient"]) if latest and latest["correlation_coefficient"] is not None else None,
                "sample_size": latest["sample_size"] if latest else None,
                "window_end": latest["window_end"].isoformat() if latest else None,
            })

    return {"success": True, "data": {"symbol": symbol, "items": items}}


@router.get("/spillover-radar", summary="輪動外溢雷達清單（§4.3 篩選結果 + 跟漲勝率）")
async def get_spillover_radar(chain_id: Optional[str] = None):
    _check_enabled()
    from db.session import get_async_session
    from industry_chain import spillover

    async with get_async_session() as session:
        items = await spillover.build_radar(chain_id, session)

    return {"success": True, "data": {"items": items}}


@router.post("/extract/trigger", summary="手動觸發 LLM 產業鏈萃取（單鏈或全部）")
async def trigger_extract(req: ExtractTriggerRequest):
    _check_enabled()
    from industry_chain.extractor import extract_chain

    if req.chain_id:
        result = await extract_chain(req.chain_id, provider_code=req.provider, model=req.model)
        return {"success": True, "data": result}

    # 全部鏈：比照排程工作的錯誤隔離慣例，單鏈失敗（含閘門類例外，如已達月上限）不影響其餘鏈，
    # 全部彙整回傳讓呼叫端一次看到整體結果，而不是第一條鏈就把整個請求打斷
    results = []
    for chain in ic_config.load_chains():
        try:
            result = await extract_chain(chain.chain_id, provider_code=req.provider, model=req.model)
            results.append(result)
        except Exception as e:
            results.append({"status": "error", "chain_id": chain.chain_id, "error": str(e)})
    return {"success": True, "data": {"items": results}}
