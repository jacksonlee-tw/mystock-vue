"""
industry_chain/graph.py
純 Python 鄰接表 + BFS（見 docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §4.3.2、
ADR-IC-02）。單一產業鏈通常僅數十檔標的，不需要 networkx（§2.4 已評估過）。

不吃 DB、不做 I/O：邊資料一律由呼叫端（spillover.py）先查好再傳入，本模組只負責圖遍歷。
"""
from __future__ import annotations


def bfs_upstream_candidates(edges: list[dict], root_symbols: list[str], max_tier: int) -> list[dict]:
    """從 `root_symbols`（下游龍頭）出發，沿 `downstream_symbol -> upstream_symbol` 方向逐層往
    上游走，收集 `relation_tier` 恰好等於當前層數的邊，直到 `max_tier`。

    `relation_tier` 是邊資料本身既有的屬性（由 LLM 萃取或人工標註時就決定），不是本函式重新
    計算的 BFS 深度——兩者在正常資料下應該一致，但本函式刻意以「邊的 tier 屬性」為準，而非
    單純以走訪步數為準：如果同一個標的同時被兩條鏈路連到（一條經 tier1、一條經 tier2），
    仍分別以各自邊上標註的 tier 呈現，不強制去重成單一層級。

    回傳的邊之間沒有順序保證；同一條邊不會重複出現兩次。
    """
    by_downstream: dict[str, list[dict]] = {}
    for e in edges:
        by_downstream.setdefault(e["downstream_symbol"], []).append(e)

    collected: list[dict] = []
    seen_edge_ids: set = set()
    frontier: set[str] = set(root_symbols)
    visited_symbols: set[str] = set(root_symbols)

    for tier in range(1, max_tier + 1):
        next_frontier: set[str] = set()
        for symbol in frontier:
            for e in by_downstream.get(symbol, []):
                if e["relation_tier"] != tier:
                    continue
                key = e.get("id", (e["upstream_symbol"], e["downstream_symbol"]))
                if key in seen_edge_ids:
                    continue
                seen_edge_ids.add(key)
                collected.append(e)
                up = e["upstream_symbol"]
                if up not in visited_symbols:
                    next_frontier.add(up)
                    visited_symbols.add(up)
        frontier = next_frontier
        if not frontier:
            break

    return collected
