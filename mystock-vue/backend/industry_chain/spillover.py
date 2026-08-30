"""
industry_chain/spillover.py
動能外溢與補漲偵測（見 docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §4.3）。

點火偵測直接查既有 alert_repository，不新增偵測邏輯（ADR-IC-03）；估值／營收濾網直接呼叫
strategies/conditions_pick.py 的既有私有判斷函式，不重算（規格書「不得自行重算」鐵則）；
跟漲勝率是簡單事件統計，不是回測（ADR-IC-08）。
"""
from __future__ import annotations
import logging
from datetime import date

from industry_chain import config as ic_config
from industry_chain import graph as ic_graph
from industry_chain.lead_lag_job import price_series
from repositories.alert_repository import query_alerts
from repositories.industry_chain_repository import IndustryChainRepository
from services.chip_provider import ChipDataProvider
from strategies.conditions_pick import _eval_revenue_growth, _eval_valuation_filter

logger = logging.getLogger("mystock-backend")

# FR-12：估值歷史只回補近 3 個月，分位數濾網暫以絕對門檻代替（ADR-IC-07，直接沿用《相對低點》結論）
DEFAULT_PE_MAX = 25.0
DEFAULT_REVENUE_YOY_MIN = 0.0
VOLUME_CONTRACTION_MAX = 1.0  # 短均量／長均量 < 1 視為量縮


async def get_ignited_leaders(chain) -> list[dict]:
    """FR-11：查今天是否有 chain.downstream_leaders 任一標的的警示紀錄（不新增偵測邏輯，
    ADR-IC-03）。回傳 [{"symbol", "alerts": [...]}]，只含真的有點火的 leader。"""
    today = date.today().isoformat()
    ignited = []
    for leader in chain.downstream_leaders:
        alerts = [a for a in query_alerts(symbol=leader, days=1) if a.get("trade_date") == today]
        if alerts:
            ignited.append({"symbol": leader, "alerts": alerts})
    return ignited


async def _evaluate_candidate_filters(symbol: str, market: str = "tw") -> dict | None:
    """對候選標的套用 FR-12/13/14 三個濾網。任一濾網因資料缺失回傳 None（無法評估）就整個
    候選排除（AC-IC-10：不得靜默以預設值代入）。回傳三個濾網各自的通過與否＋細節。"""
    ctx = await ChipDataProvider().get_bars(
        symbol, market, ma_periods=[20, 60], volume_ma_period=20, with_valuation=True,
    )
    if ctx is None or ctx.length == 0:
        return None
    idx = ctx.length - 1

    valuation = _eval_valuation_filter(ctx, idx, {"pe_max": DEFAULT_PE_MAX})
    revenue = _eval_revenue_growth(ctx, idx, {"yoy_min": DEFAULT_REVENUE_YOY_MIN})

    from indicators.chip import volume_contraction_ratio
    vol_ratio = volume_contraction_ratio(ctx.volumes, idx, short_window=20, long_window=60)

    return {
        "valuation": {"pass": valuation is not None, "details": valuation},
        "revenue": {"pass": revenue is not None, "details": revenue},
        "volume": {
            "pass": vol_ratio is not None and vol_ratio < VOLUME_CONTRACTION_MAX,
            "details": {"ratio": vol_ratio},
        },
    }


async def _win_rate_for_candidate(leader: str, candidate: str, market: str, peak_lag_days: int | None) -> dict | None:
    """§4.3.3 簡單事件統計（ADR-IC-08，非回測）：對 leader 過去所有點火事件，檢查候選標的
    在 peak_lag_days 天窗口內（交易日，非日曆日）報酬是否為正。peak_lag_days 未知時無法定義
    窗口，直接回傳 None（不得用猜的天數代入）。"""
    if not peak_lag_days:
        return None
    history = query_alerts(symbol=leader, days=None)  # days=None：不設日期下限，取全部歷史
    ignition_dates = sorted({a["trade_date"] for a in history if a.get("trade_date")})
    if not ignition_dates:
        return None

    dates, closes = await price_series(candidate, market)
    date_to_idx = {d: i for i, d in enumerate(dates)}

    wins = total = 0
    for d in ignition_dates:
        idx = date_to_idx.get(d)
        if idx is None:
            continue
        target_idx = idx + peak_lag_days
        if target_idx >= len(closes):
            continue
        total += 1
        if closes[target_idx] > closes[idx]:
            wins += 1

    if total == 0:
        return None
    return {"wins": wins, "total": total, "rate": wins / total}


async def build_radar(chain_id: str | None, session) -> list[dict]:
    """組裝雷達清單。`chain_id` 為 None 時跨全部鏈彙整。"""
    repo = IndustryChainRepository(session)
    chains = ic_config.load_chains()
    if chain_id:
        chains = [c for c in chains if c.chain_id == chain_id]

    max_tier = ic_config.get_max_bfs_tier()
    require_verified = ic_config.require_verified_edge()

    items: list[dict] = []
    for chain in chains:
        if not chain.downstream_leaders:
            continue
        ignited = await get_ignited_leaders(chain)
        if not ignited:
            continue

        all_edges = await repo.list_edges(chain_id=chain.chain_id)
        if require_verified:
            all_edges = [e for e in all_edges if e["is_verified"]]

        edge_by_pair = {(e["upstream_symbol"], e["downstream_symbol"]): e for e in all_edges}

        for ig in ignited:
            candidates = ic_graph.bfs_upstream_candidates(all_edges, [ig["symbol"]], max_tier)
            for edge in candidates:
                filters = await _evaluate_candidate_filters(edge["upstream_symbol"])
                if filters is None or not all(f["pass"] for f in filters.values()):
                    continue  # AC-IC-10：任一濾網未過或無法評估就排除，不進清單

                cache_rows = await repo.list_lead_lag_for_edge(edge["id"])
                latest = cache_rows[0] if cache_rows else None
                peak_lag_days = latest["peak_lag_days"] if latest else None

                win_rate = await _win_rate_for_candidate(
                    ig["symbol"], edge["upstream_symbol"], edge["upstream_market"], peak_lag_days,
                )

                items.append({
                    "chain_id": chain.chain_id,
                    "downstream_leader": ig["symbol"],
                    "symbol": edge["upstream_symbol"],
                    "relation_tier": edge["relation_tier"],
                    "component_type": edge["component_type"],
                    "source": edge["source"],
                    "is_verified": edge["is_verified"],
                    "filters": filters,
                    "peak_lag_days": peak_lag_days,
                    "correlation_coefficient": float(latest["correlation_coefficient"]) if latest and latest["correlation_coefficient"] is not None else None,
                    "sample_size": latest["sample_size"] if latest else None,
                    "win_rate": win_rate,
                })

    return items


async def compute_node_states(chain, edges: list[dict], radar_items: list[dict]) -> dict[str, str]:
    """供 `GET /{chain_id}/graph` 使用：downstream_leaders 中今天有點火的標為 "ignited"；
    出現在雷達候選清單中的標為 "candidate"；其餘 "dormant"。"""
    ignited = await get_ignited_leaders(chain)
    ignited_symbols = {i["symbol"] for i in ignited}
    candidate_symbols = {item["symbol"] for item in radar_items if item["chain_id"] == chain.chain_id}

    node_symbols: set[str] = set(chain.downstream_leaders)
    for e in edges:
        node_symbols.add(e["upstream_symbol"])
        node_symbols.add(e["downstream_symbol"])

    states: dict[str, str] = {}
    for symbol in node_symbols:
        if symbol in ignited_symbols:
            states[symbol] = "ignited"
        elif symbol in candidate_symbols:
            states[symbol] = "candidate"
        else:
            states[symbol] = "dormant"
    return states
