"""
industry_chain/summary.py
`extract_industry_chain_summary()`（見 docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md
§4.4 FR-15）——把「這檔標的目前在產業鏈輪動脈絡裡處於什麼位置」整理成一份精簡 JSON，供
ai/summary.py 當作 quant_summary 的一個新選用欄位（`industry_chain_context`），最終餵給既有
個股診股報告的 User Prompt（FR-16，見 ai/prompt.py）。

刻意直接複用 spillover.build_radar() 的候選判定與跟漲勝率邏輯，不另外重新走一遍
BFS／濾網——這裡要回答的問題本質跟雷達清單相同，只是視角從「全部候選」換成「單一標的」，
沒有理由維護第二套篩選邏輯（比照策略引擎「條件函式只讀既算好序列」的同一條精神）。

呼叫端（ai/summary.py）負責：① 只在 market == "tw" 時呼叫（本模組僅涵蓋台股，§1.3）；
② 先檢查 industry_chain.config.is_enabled()，未啟用時完全不呼叫本模組、不觸碰資料庫
（AC-IC-15）；③ 用 try/except 包住整段呼叫，任何失敗（含 Postgres 不可用，ADR-IC-01：
本模組讀取面需要 Postgres）一律視為「查無資料」，不得讓整份診股報告因此中止——這是選用的
錦上添花欄位，不是報告能否產生的必要條件。
"""
from __future__ import annotations
from typing import Any, Optional

from industry_chain import config as ic_config
from industry_chain.spillover import build_radar, get_ignited_leaders
from repositories.industry_chain_repository import IndustryChainRepository


async def extract_industry_chain_summary(symbol: str, session) -> Optional[dict[str, Any]]:
    """回傳 `{"chains": [...]}`；`symbol` 不落在任何已核定的產業鏈骨架內時回傳 None
    （呼叫端據此決定要不要寫入 quant_summary，比照既有 recent_alerts「查無則不寫欄位」慣例，
    不寫入一個空陣列去佔位）。

    每個鏈項目視 `symbol` 的角色分兩種形狀：
    - 下游龍頭（`role="downstream_leader"`）：`ignited_today` 為今天是否已有點火警示
      （直接複用 FR-11 既有點火判定，ADR-IC-03，不重新偵測）。
    - 上游供應商（`role="upstream_supplier"`）：`relation_tier`／`supplies_to`／
      `component_type`／`is_verified` 描述這條邊本身；`rotation_candidate` 為 True 時，
      代表這檔標的今天通過 FR-12/13/14 全部濾網、是某個已點火下游龍頭的補漲候選
      （見 spillover.build_radar()），並附上 `peak_lag_days`／`correlation_coefficient`／
      `historical_win_rate`（樣本數不足時 `historical_win_rate` 為 None，呼叫端／Prompt
      不得把小樣本勝率當成有統計意義的結論，比照 AC-IC-9 精神）。
    """
    repo = IndustryChainRepository(session)
    chains = ic_config.load_chains()
    require_verified = ic_config.require_verified_edge()

    # 跨鏈算一次，供下面依 (symbol, chain_id) 查表複用，避免逐鏈重算一次 build_radar()
    # 內部就要對候選標的各自打一次 ChipDataProvider（見該函式對 P0/P1 資料量的既有評估）。
    all_radar_items = await build_radar(None, session)
    radar_by_key = {(item["symbol"], item["chain_id"]): item for item in all_radar_items}

    result_chains: list[dict[str, Any]] = []
    for chain in chains:
        edges = await repo.list_edges(chain_id=chain.chain_id)
        if require_verified:
            edges = [e for e in edges if e["is_verified"]]

        is_downstream_leader = symbol in chain.downstream_leaders
        own_upstream_edges = [e for e in edges if e["upstream_symbol"] == symbol]
        if not is_downstream_leader and not own_upstream_edges:
            continue  # 這條鏈跟本標的無關，不列入——避免塞進一堆「查無關聯」的雜訊給 Prompt

        entry: dict[str, Any] = {"chain_id": chain.chain_id, "chain_name": chain.name}

        if is_downstream_leader:
            ignited = await get_ignited_leaders(chain)
            entry["role"] = "downstream_leader"
            entry["ignited_today"] = any(i["symbol"] == symbol for i in ignited)
        else:
            # 同一標的在同一條鏈裡可能對多個下游龍頭供貨、關聯層級不同；取關聯層級最淺
            # （tier 最小＝離下游龍頭最近）的一筆代表本標的在這條鏈的主要定位
            best_edge = min(own_upstream_edges, key=lambda e: e["relation_tier"])
            entry["role"] = "upstream_supplier"
            entry["relation_tier"] = best_edge["relation_tier"]
            entry["supplies_to"] = best_edge["downstream_symbol"]
            entry["component_type"] = best_edge["component_type"]
            entry["is_verified"] = best_edge["is_verified"]

            radar_item = radar_by_key.get((symbol, chain.chain_id))
            entry["rotation_candidate"] = radar_item is not None
            if radar_item:
                entry["ignited_downstream_leader"] = radar_item["downstream_leader"]
                entry["peak_lag_days"] = radar_item["peak_lag_days"]
                entry["correlation_coefficient"] = radar_item["correlation_coefficient"]
                entry["historical_win_rate"] = radar_item["win_rate"]

        result_chains.append(entry)

    if not result_chains:
        return None
    return {"chains": result_chains}
