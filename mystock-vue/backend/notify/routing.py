"""
notify/routing.py
M2 訂閱路由（§4.4）
resolve_endpoints()：接受 event + routing_facts，依訂閱規則展開目標端點清單
MATCHER_REGISTRY：可比對的條件比對函數（Phase 3 擴充各種過濾條件）
鐵則 R3：routing.py 不得 import channels/
"""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger("mystock-backend")


# ── Matcher 可組合的條件函數 ──────────────────────────────────
# signature: (fact_value, condition_value) -> bool
# Phase 1：僅 "accept_all" 規則（無過濾條件 → True）
# Phase 3：擴充 market / signal_type / signal_strength / strategy_category / stock_id

def _match_accept_all(_fact: Any, _cond: Any) -> bool:
    return True

def _match_in_list(fact: Any, cond_list: list) -> bool:
    """事實值在清單中"""
    return str(fact) in [str(c) for c in cond_list]

def _match_not_in_list(fact: Any, cond_list: list) -> bool:
    return str(fact) not in [str(c) for c in cond_list]

def _match_equals(fact: Any, cond_val: Any) -> bool:
    return str(fact).lower() == str(cond_val).lower()


MATCHER_REGISTRY: dict[str, callable] = {
    "in_list":     _match_in_list,
    "not_in_list": _match_not_in_list,
    "equals":      _match_equals,
}

# filter_conditions 鍵 → routing_facts 鍵的對應（§4.4 比對快照欄位）
CONDITION_FACT_KEYS = {
    "markets":              "market",
    "signal_types":         "signal_type",
    "signal_strengths":     "signal_strength",
    "strategy_categories":  "strategy_category",
    "strategy_ids":         "strategy_id",
    "stock_ids":            "stock_id",
    "severities":           "severity",
}


def _matches_subscription(rule: dict, facts: dict) -> bool:
    """
    判斷一條訂閱規則的 filter_conditions 是否符合路由事實。
    Phase 1：filter_conditions 為空 dict → 全收（Accept All）。
    Phase 3：各欄位以 in_list 方式過濾。
    """
    conditions: dict = rule.get("filter_conditions") or {}
    if not conditions:
        return True  # Phase 1：全收規則

    for cond_key, fact_key in CONDITION_FACT_KEYS.items():
        cond_val = conditions.get(cond_key)
        if cond_val is None:
            continue
        fact_val = facts.get(fact_key, "")
        # 條件值為清單時使用 in_list；否則 equals
        if isinstance(cond_val, list):
            if not _match_in_list(fact_val, cond_val):
                return False
        else:
            if not _match_equals(fact_val, cond_val):
                return False
    return True


# ── resolve_endpoints ─────────────────────────────────────────
async def resolve_endpoints(
    event_type: str,
    facts: dict,
    repo: Any,           # notify_repository（Type hint 不直接 import 以符合鐵則 R3）
) -> list[dict]:
    """
    依訂閱規則展開目標端點清單（§4.4）。
    回傳 endpoint row list（來自 notify_endpoint），每個 dict 附帶 matched_rule_code。
    """
    # 1. 載入啟用的訂閱規則（依事件類型過濾）
    rules = await repo.list_subscriptions_by_event_type(event_type)

    endpoint_set: dict[int, dict] = {}  # endpoint_id → endpoint row

    for rule in rules:
        if not _matches_subscription(rule, facts):
            continue

        # 2. 展開群組 / 收件人 / 端點
        endpoints = await _expand_rule_targets(rule, repo)
        for ep in endpoints:
            ep_id = ep.get("id")
            if ep_id and ep_id not in endpoint_set:
                ep["_matched_rule_code"] = rule.get("rule_code", "")
                endpoint_set[ep_id] = ep

    result = list(endpoint_set.values())
    logger.debug(
        "[通知] 路由結果：event_type=%s，符合端點 %d 個（規則 %d 條）",
        event_type, len(result), len(rules)
    )
    return result


async def _expand_rule_targets(rule: dict, repo: Any) -> list[dict]:
    """展開訂閱規則目標（群組 / 收件人 / 端點）為端點清單"""
    group_id     = rule.get("target_group_id")
    recipient_id = rule.get("target_recipient_id")
    endpoint_id  = rule.get("target_endpoint_id")

    if endpoint_id:
        ep = await repo.get_endpoint(endpoint_id)
        return [ep] if ep else []

    if recipient_id:
        eps = await repo.list_endpoints_for_recipient(recipient_id)
        return eps

    if group_id:
        members = await repo.list_group_members(group_id)
        all_eps = []
        for m in members:
            eps = await repo.list_endpoints_for_recipient(m["recipient_id"])
            all_eps.extend(eps)
        return all_eps

    return []


async def preview_subscription(
    rule_code: str,
    event_type: str,
    sample_facts: dict,
    repo: Any,
) -> dict:
    """
    POST /subscriptions/preview — 用示範事實測試訂閱規則是否命中（UC-10）
    """
    rules = await repo.list_subscriptions_by_event_type(event_type)
    target = next((r for r in rules if r.get("rule_code") == rule_code), None)
    if not target:
        return {"matched": False, "reason": "規則不存在"}
    matched = _matches_subscription(target, sample_facts)
    return {
        "matched": matched,
        "rule_code": rule_code,
        "facts_used": sample_facts,
    }
