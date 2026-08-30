"""
industry_chain/validator.py
LLM 萃取結果的五道機器校驗（見 docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §4.7.4）。

寫入資料庫**之前**必須全部通過。校驗二（代碼↔名稱一致性）是最重要的一道——幻覺的典型型態
不是「掰出不存在的公司」，而是「公司對、代號記錯」，這種錯誤在 UI 上完全看不出來。
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

from industry_chain.schema import ChainExtractionResult

_NAME_STRIP_PATTERN = re.compile(r"(股份有限公司|-KY|\s+)")


def _normalize_name(name: str) -> str:
    return _NAME_STRIP_PATTERN.sub("", name or "").strip()


@dataclass
class RejectedEdge:
    upstream_symbol: str
    downstream_symbol: str
    reason: str


@dataclass
class ValidationOutcome:
    accepted: list[dict] = field(default_factory=list)   # 可直接餵給 dual_write_industry_chain_edges()
    rejected: list[RejectedEdge] = field(default_factory=list)
    batch_rejected: str | None = None  # 非 None 時代表 V5 整批退件的原因，accepted/rejected 皆為空


async def validate_extraction(
    result: ChainExtractionResult, *, chain_id: str, truncated: bool,
    max_edges: int = 80, market: str = "tw",
) -> ValidationOutcome:
    # V5（整批性質，優先檢查）：回應被截斷或單鏈邊數超過上限，部分寫入是明確的失敗，
    # 不是可接受的降級（規格書 §4.7.4 V5、AC-IC-21）。
    if truncated:
        return ValidationOutcome(batch_rejected="回應被截斷（stop_reason=max_tokens），JSON 可能不完整")
    if len(result.edges) > max_edges:
        return ValidationOutcome(batch_rejected=f"單鏈邊數 {len(result.edges)} 超過上限 {max_edges}")

    if result.chain_id != chain_id:
        # 模型回傳的 chain_id 與送出值不一致：不讓模型有機會創造新的 chain_id，整批視為不可信
        return ValidationOutcome(batch_rejected=f"回應 chain_id（{result.chain_id}）與請求不一致（{chain_id}）")

    # V1：批次查詢所有出現的代碼是否存在於 symbols（一次查完，不逐筆打 DB）
    from repositories.stock_repository import StockRepository
    codes = sorted({e.upstream_symbol for e in result.edges} | {e.downstream_symbol for e in result.edges})
    existing_rows = await StockRepository().get_symbols(codes, market) if codes else []
    existing_by_code = {row["symbol"]: row for row in existing_rows}

    accepted: list[dict] = []
    rejected: list[RejectedEdge] = []
    seen_pairs: set[tuple[str, str]] = set()
    seen_reverse: set[tuple[str, str]] = set()

    for e in result.edges:
        up, down = e.upstream_symbol, e.downstream_symbol

        # V3：結構合法性 —— 自環
        if up == down:
            rejected.append(RejectedEdge(up, down, "自環（upstream == downstream）"))
            continue

        # V1：代碼存在性
        up_row = existing_by_code.get(up)
        down_row = existing_by_code.get(down)
        if up_row is None:
            rejected.append(RejectedEdge(up, down, f"代碼不存在於 symbols：{up}"))
            continue
        if down_row is None:
            rejected.append(RejectedEdge(up, down, f"代碼不存在於 symbols：{down}"))
            continue

        # V2：代碼↔名稱一致性（正規化後比對包含關係，允許簡稱）
        up_norm, down_norm = _normalize_name(up_row.get("name", "")), _normalize_name(down_row.get("name", ""))
        up_llm_norm, down_llm_norm = _normalize_name(e.upstream_name), _normalize_name(e.downstream_name)
        if not up_norm or (up_norm not in up_llm_norm and up_llm_norm not in up_norm):
            rejected.append(RejectedEdge(up, down, f"名稱不符：{up} 應為「{up_row.get('name')}」，模型給的是「{e.upstream_name}」"))
            continue
        if not down_norm or (down_norm not in down_llm_norm and down_llm_norm not in down_norm):
            rejected.append(RejectedEdge(up, down, f"名稱不符：{down} 應為「{down_row.get('name')}」，模型給的是「{e.downstream_name}」"))
            continue

        # V4：層級合法性（Pydantic 的 Literal[1, 2] 已保證型別，這裡只需再次確認範圍語意）
        if e.relation_tier not in (1, 2):
            rejected.append(RejectedEdge(up, down, f"relation_tier 超出範圍：{e.relation_tier}"))
            continue

        # V3：批內去重、批內方向矛盾（A→B 與 B→A 兩筆皆丟，無從判斷哪筆對）
        pair = (up, down)
        if pair in seen_pairs:
            rejected.append(RejectedEdge(up, down, "批內重複"))
            continue
        if (down, up) in seen_pairs:
            rejected.append(RejectedEdge(up, down, f"批內方向矛盾：同時出現 {up}→{down} 與 {down}→{up}"))
            # 反向那筆已經被 accepted，需要回頭撤銷；連同它也記一筆 rejected，
            # 否則活動紀錄的「N 筆遭拒」會少算已被撤銷的那一筆，跟實際被剔除的邊數對不上
            accepted[:] = [a for a in accepted if not (a["upstream_symbol"] == down and a["downstream_symbol"] == up)]
            rejected.append(RejectedEdge(down, up, f"批內方向矛盾：同時出現 {up}→{down} 與 {down}→{up}"))
            seen_reverse.add(pair)
            continue
        if pair in seen_reverse:
            continue
        seen_pairs.add(pair)

        accepted.append({
            "chain_id": chain_id,
            "upstream_symbol": up,
            "downstream_symbol": down,
            "upstream_market": market,
            "downstream_market": market,
            "relation_tier": e.relation_tier,
            "component_type": e.component_type,
            "is_verified": False,  # ADR-IC-14：LLM 來源一律強制 FALSE，不接受任何捷徑
            "extra_data": {
                "llm_confidence": e.confidence,
                "llm_evidence": e.evidence,
            },
        })

    return ValidationOutcome(accepted=accepted, rejected=rejected)
