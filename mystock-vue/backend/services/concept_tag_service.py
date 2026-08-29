"""概念股標籤（見 docs/17.熱力圖概念股標籤分類/概念股標籤分類_規劃書.md）。

跟「產業分類」（services/industry_fetcher.py，1:1、TWSE/TPEx 官方來源、自動抓取）是兩個不同的
分類維度：概念標籤是多對多、非官方、需要人工維護（例如「AI」「記憶體」「CPO矽光子」這種主題式
分類），沒有公開資料源可以抓，Phase 1 純粹讀取人工維護的 JSON 種子檔（規劃書 ADR-CT4），不提供
任何寫入/同步 API。

儲存比照 industries.json 的既有慣例（規劃書 ADR-CT1）：JSON 落在 data/{market}/_meta/
concept_tags.json，不受 DATA_SOURCE 開關影響、不需要 Postgres migration。檔案結構：
    {
        "tags": [{"id", "name", "color", "sort_order"}, ...],
        "symbol_tags": {"<symbol>": ["<tag_id>", ...], ...}
    }
`tags[].color` 直接沿用 frontend useWatchlistTags.js 既有的 6 色 Tailwind 色票 key
（slate/violet/amber/emerald/rose/sky），前端可共用同一份色彩對照，不用另建一套。
"""
import json
import logging
import os
from typing import Dict, List

from config import DATA_DIR

logger = logging.getLogger("mystock-backend")

_META_DIR_NAME = "_meta"
_CONCEPT_TAGS_FILE = "concept_tags.json"

_VALID_COLORS = {"slate", "violet", "amber", "emerald", "rose", "sky"}

_EMPTY: Dict[str, object] = {"tags": [], "symbol_tags": {}}


def concept_tags_json_path(market: str) -> str:
    market_dir = os.path.join(DATA_DIR, market, _META_DIR_NAME)
    os.makedirs(market_dir, exist_ok=True)
    return os.path.join(market_dir, _CONCEPT_TAGS_FILE)


def load_concept_tags_json(market: str) -> Dict[str, object]:
    """讀取並驗證概念標籤種子檔。檔案不存在、格式錯誤，或內容有問題（tag id 重複、
    symbol_tags 引用不存在的 tag id）一律優雅降級為空結果（比照 load_industries_json()
    「查無資料就回傳空字典，不讓整支 API 500」的既有慣例，見 ADR-CT1 代價與對策），
    只在 log 記警告，不阻斷熱力圖本體或「依產業」分組。"""
    path = concept_tags_json_path(market)
    if not os.path.exists(path):
        return {"tags": [], "symbol_tags": {}}

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        logger.warning(f"[概念標籤] 讀取 {path} 失敗，退回無標籤分組: {e}")
        return {"tags": [], "symbol_tags": {}}

    return _validate(raw, market)


def _validate(raw: object, market: str) -> Dict[str, object]:
    if not isinstance(raw, dict):
        logger.warning(f"[概念標籤] {market} 的 concept_tags.json 頂層不是物件，退回無標籤分組")
        return {"tags": [], "symbol_tags": {}}

    raw_tags = raw.get("tags")
    raw_symbol_tags = raw.get("symbol_tags")
    if not isinstance(raw_tags, list) or not isinstance(raw_symbol_tags, dict):
        logger.warning(f"[概念標籤] {market} 的 concept_tags.json 缺少 tags/symbol_tags 欄位，退回無標籤分組")
        return {"tags": [], "symbol_tags": {}}

    tags: List[dict] = []
    seen_ids = set()
    for item in raw_tags:
        if not isinstance(item, dict):
            continue
        tag_id = item.get("id")
        name = item.get("name")
        if not tag_id or not name:
            continue
        if tag_id in seen_ids:
            logger.warning(f"[概念標籤] {market} 的 tag id 重複：{tag_id}，僅保留第一筆")
            continue
        seen_ids.add(tag_id)
        color = item.get("color")
        if color not in _VALID_COLORS:
            color = "slate"
        tags.append({
            "id": tag_id,
            "name": name,
            "color": color,
            "sort_order": item.get("sort_order", 0),
        })
    tags.sort(key=lambda t: t["sort_order"])

    symbol_tags: Dict[str, List[str]] = {}
    for symbol, tag_ids in raw_symbol_tags.items():
        if not isinstance(tag_ids, list):
            continue
        valid_ids = [t for t in tag_ids if t in seen_ids]
        dropped = set(tag_ids) - set(valid_ids)
        if dropped:
            logger.warning(f"[概念標籤] {market}/{symbol} 引用不存在的 tag id：{sorted(dropped)}，已忽略")
        if valid_ids:
            symbol_tags[symbol] = valid_ids

    return {"tags": tags, "symbol_tags": symbol_tags}
