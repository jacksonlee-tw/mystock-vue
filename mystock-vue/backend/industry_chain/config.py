"""
industry_chain/config.py
產業鏈骨架設定（YAML）與功能旗標讀取（見 docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md
§6）。

兩者分工：YAML 管「產業鏈長什麼樣」（人工審閱、隨投資觀點調整）；.env 管「功能開不開」
（部署層設定）。YAML 每次呼叫重新解析、不快取（比照 strategies/config_loader.py 的既有
慣例：檔案小、掃描頻率低，改門檻免重啟）；找不到檔案或格式錯誤一律記警告、降級回傳空清單，
不讓服務掛掉。

本批次（第一批交付）只有 is_enabled()／load_chains()／get_chain()：INDUSTRY_CHAIN_ENABLED
目前尚無任何呼叫端讀取（排程工作與 API 留待後續批次接上），先建好這個模組的骨架供後續
extractor.py／graph.py／spillover.py 共用，避免每支後續模組各自重寫一份 YAML 載入邏輯。
"""
from __future__ import annotations
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

import yaml
from dotenv import load_dotenv

from industry_chain.errors import IndustryChainConfigInvalidException

logger = logging.getLogger("mystock-backend")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
CHAINS_YAML_PATH = os.path.join(BASE_DIR, "industry_chain_config", "industry_chains.yaml")


def _env(key: str, default: str = "") -> str:
    load_dotenv(ENV_PATH, override=True)
    return os.getenv(key, default).strip()


def _env_bool(key: str, default: bool = False) -> bool:
    return _env(key, str(default)).lower() in ("true", "1", "yes")


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


# ── 總開關 ──────────────────────────────────────────────────────
def is_enabled() -> bool:
    return _env_bool("INDUSTRY_CHAIN_ENABLED", False)


# ── 篩選行為（§6.2；上一批文件已引用但沒有讀取端，這批補上）───────
def get_max_bfs_tier() -> int:
    return _env_int("IC_MAX_BFS_TIER", 2)


def require_verified_edge() -> bool:
    return _env_bool("IC_REQUIRE_VERIFIED_EDGE", True)


# ── 兩段式 grounded 萃取（§4.7.7，ADR-IC-17）─────────────────────
def grounding_enabled() -> bool:
    return _env_bool("IC_LLM_GROUNDING_ENABLED", False)


def get_research_model() -> str:
    """留空時沿用呼叫端（extractor.py）已經幫 Stage B 解析出的模型，不是去讀一個獨立的
    `IC_LLM_MODEL`——那個設定項在 P0 實作裡從未存在過，模型一律由呼叫端以參數傳入或退回
    Provider 預設（見 §4.7 開發過程的落差修正紀錄）。"""
    return _env("IC_LLM_RESEARCH_MODEL", "")


def get_extract_model() -> str:
    """Stage B（`extract_chain()`）LLM 知識萃取在呼叫端未指定 `model` 時的預設模型，僅適用
    provider=gemini。獨立於 `ai/config.py` 的 `GEMINI_MODEL`——後者是「AI 技術分析報告」
    （ai_analysis）共用的全站預設，兩個功能各自的模型選型與升級步調不同步，不應共用同一個
    全域鍵值（例如本模組想先行升級到新機型，不該連帶把 ai_analysis 的預設也換掉）。
    留空則退回 `ai_config.get_gemini_model()`，行為與加這個設定前一致。"""
    return _env("IC_LLM_EXTRACT_MODEL", "")


def get_research_lookback_months() -> int:
    return _env_int("IC_LLM_RESEARCH_LOOKBACK_MONTHS", 12)


def get_grounding_timeout_sec() -> int:
    return _env_int("IC_LLM_REQUEST_TIMEOUT_SEC", 180)


# ── 產業鏈骨架（YAML）────────────────────────────────────────────
@dataclass
class ChainDef:
    chain_id: str
    name: str
    downstream_leaders: list[str] = field(default_factory=list)
    lead_lag_window_days: list[int] = field(default_factory=lambda: [1, 30])
    extraction_hint: str = ""
    note: str = ""  # 維護對話框用的備註欄位（見 §「新增類別」對話紀錄）；不影響萃取/篩選邏輯


_EMPTY_DEFAULTS = {"lead_lag_window_days": [1, 30], "decouple_threshold": 0.1, "decouple_check_window_days": 60}


def _load_yaml_raw() -> Optional[dict]:
    """讀檔＋解析，找不到檔案或語法錯誤一律記警告回傳 None。`load_chains()`／`get_defaults()`
    共用同一份讀檔邏輯，避免兩處各自重讀一次檔案、降級判斷邏輯還可能兜不起來。"""
    if not os.path.exists(CHAINS_YAML_PATH):
        logger.warning(f"[產業鏈] 設定檔不存在: {CHAINS_YAML_PATH}")
        return None
    try:
        with open(CHAINS_YAML_PATH, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"[產業鏈] 設定檔解析失敗，降級為空清單: {e}")
        return None
    if not isinstance(raw, dict):
        logger.warning("[產業鏈] 設定檔格式錯誤（頂層應為物件），降級為空清單")
        return None
    return raw


def get_defaults() -> dict:
    """回傳 YAML `defaults` 區塊（`lead_lag_window_days`／`decouple_threshold`／
    `decouple_check_window_days`）。缺漏或格式錯誤的欄位個別退回 `_EMPTY_DEFAULTS` 的對應值，
    不因單一欄位寫壞就整個降級。"""
    raw = _load_yaml_raw()
    defaults = (raw or {}).get("defaults") or {}
    if not isinstance(defaults, dict):
        defaults = {}
    return {
        "lead_lag_window_days": defaults.get("lead_lag_window_days", _EMPTY_DEFAULTS["lead_lag_window_days"]),
        "decouple_threshold": defaults.get("decouple_threshold", _EMPTY_DEFAULTS["decouple_threshold"]),
        "decouple_check_window_days": defaults.get(
            "decouple_check_window_days", _EMPTY_DEFAULTS["decouple_check_window_days"]
        ),
    }


def load_chains() -> list[ChainDef]:
    """讀取 industry_chain_config/industry_chains.yaml 的 `chains` 清單。找不到檔案、YAML
    語法錯誤，或內容不是預期結構時，一律記警告並回傳空清單——比照
    config_loader.load_strategy_config() 的既有降級慣例，不讓一份寫壞的 YAML 拖垮整個服務。"""
    raw = _load_yaml_raw()
    if raw is None:
        return []

    default_window = get_defaults()["lead_lag_window_days"]

    chains_raw = raw.get("chains")
    if not isinstance(chains_raw, list):
        logger.warning("[產業鏈] 設定檔缺少 chains 清單，降級為空清單")
        return []

    result: list[ChainDef] = []
    for item in chains_raw:
        if not isinstance(item, dict) or not item.get("chain_id"):
            logger.warning(f"[產業鏈] 跳過格式不正確的鏈定義: {item!r}")
            continue
        result.append(ChainDef(
            chain_id=str(item["chain_id"]),
            name=str(item.get("name") or item["chain_id"]),
            downstream_leaders=[str(s) for s in (item.get("downstream_leaders") or [])],
            lead_lag_window_days=item.get("lead_lag_window_days", default_window),
            extraction_hint=str(item.get("extraction_hint") or ""),
            note=str(item.get("note") or ""),
        ))
    return result


def get_chain(chain_id: str) -> Optional[ChainDef]:
    return next((c for c in load_chains() if c.chain_id == chain_id), None)


# ── 維護對話框（GET/PUT /api/v1/industry-chains/config）──────────
# 前端「管理產業鏈」對話框用來新增/編輯/刪除鏈骨架，取代手動編輯 YAML（見對話紀錄）。
# 與 load_chains() 分開一組函式的原因：load_chains() 面向掃描/排程等讀取端，
# lead_lag_window_days 缺漏時直接套用 defaults 回退；維護對話框則需要分辨「這條鏈到底有沒有
# 自己覆寫」，才知道存檔時該不該把這個欄位寫回 YAML（省略＝繼續沿用 defaults，日後改 defaults
# 會連動；寫死＝這條鏈鎖定自己的值），所以這裡刻意保留原始值、不套用回退。

_CHAIN_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")


def load_chain_config_items() -> list[dict]:
    """讀取維護對話框可編輯的欄位（不套用 lead_lag_window_days 的 defaults 回退，理由見上）。"""
    raw = _load_yaml_raw()
    if raw is None:
        return []
    chains_raw = raw.get("chains")
    if not isinstance(chains_raw, list):
        return []
    result: list[dict] = []
    for item in chains_raw:
        if not isinstance(item, dict) or not item.get("chain_id"):
            continue
        result.append({
            "chain_id": str(item["chain_id"]),
            "name": str(item.get("name") or item["chain_id"]),
            "downstream_leaders": [str(s) for s in (item.get("downstream_leaders") or [])],
            "lead_lag_window_days": item.get("lead_lag_window_days"),
            "extraction_hint": str(item.get("extraction_hint") or ""),
            "note": str(item.get("note") or ""),
        })
    return result


def validate_chain_config_items(raw_items: list[dict]) -> list[dict]:
    """驗證＋正規化維護對話框送來的整份鏈清單，通過才回傳可寫入 YAML 的乾淨版本；任一筆不合格
    就整批拒絕（存檔本來就是整份覆寫，不接受「部分成功」，否則使用者搞不清楚最後存進去的是
    哪個版本）。不驗證 downstream_leaders 的代號是否真的存在於 symbols 主檔——那需要另外查
    DB，本對話框刻意保持只操作 YAML 檔案，不依賴資料庫（見「最簡維護」的取捨）。"""
    if not isinstance(raw_items, list):
        raise IndustryChainConfigInvalidException("設定格式錯誤：應為清單")

    errors: list[str] = []
    seen_ids: set[str] = set()
    cleaned: list[dict] = []

    for idx, item in enumerate(raw_items, start=1):
        chain_id = str(item.get("chain_id") or "").strip()
        name = str(item.get("name") or "").strip()
        leaders = [s.strip() for s in (item.get("downstream_leaders") or []) if str(s).strip()]
        leaders = list(dict.fromkeys(str(s) for s in leaders))  # 去重、保留原順序
        window = item.get("lead_lag_window_days") or None
        hint = str(item.get("extraction_hint") or "").strip()
        note = str(item.get("note") or "").strip()

        if not chain_id:
            errors.append(f"第 {idx} 筆：chain_id 不可為空")
        elif not _CHAIN_ID_RE.match(chain_id):
            errors.append(f"第 {idx} 筆：chain_id「{chain_id}」只能是英數字與底線")
        elif chain_id in seen_ids:
            errors.append(f"第 {idx} 筆：chain_id「{chain_id}」重複")
        else:
            seen_ids.add(chain_id)

        if not name:
            errors.append(f"第 {idx} 筆（{chain_id or '?'}）：名稱不可為空")

        if window is not None and not (
            isinstance(window, list) and len(window) == 2
            and all(isinstance(n, int) and not isinstance(n, bool) and n > 0 for n in window)
            and window[0] <= window[1]
        ):
            errors.append(f"第 {idx} 筆（{chain_id or '?'}）：領先/落後掃描天數必須是兩個正整數（最小 ≤ 最大）")

        cleaned.append({
            "chain_id": chain_id, "name": name, "downstream_leaders": leaders,
            "lead_lag_window_days": window, "extraction_hint": hint, "note": note,
        })

    if errors:
        raise IndustryChainConfigInvalidException("；".join(errors))

    return cleaned


class _IndentDumper(yaml.SafeDumper):
    """比照原檔案排版：block 序列的 `-` 相對父層鍵縮排兩格，而不是 PyYAML 預設的
    indentless（與父層鍵同欄）。純排版考量，不影響語意。"""
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


_FILE_HEADER = (
    "# 產業鏈骨架設定（docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §6.1）\n"
    "# 只定義「鏈的骨架與參數」，實際成分股上下游關聯存於資料庫 industry_chain_edges（§5.2）；\n"
    "# 設定檔由人工審閱、變動頻率低，邊的資料隨爬取/萃取結果更新、變動頻率高，兩者分離。\n"
    "#\n"
    "# 目錄命名比照 strategy_config/，避開與 backend/config.py 撞名（見該檔案頭既有註解），\n"
    "# 路徑不採原始構想的 config/industry_chains.yaml（FR-2）。\n"
    "#\n"
    "# ⚠️ 本檔可透過「產業鏈知識圖譜」頁面的「管理產業鏈」對話框編輯，儲存時會整份覆寫\n"
    "#    （含本注釋區塊）——手動加的額外註解會在下次存檔時消失；長篇備註請改填每條鏈的\n"
    "#    note 欄位（會被保留、也會顯示在維護對話框裡）。\n"
)


def save_chain_config(items: list[dict]) -> None:
    """整份覆寫 industry_chains.yaml（維護對話框「儲存」呼叫，呼叫前務必先過
    validate_chain_config_items()）。defaults 區塊照抄目前檔案裡的既有值——本批次維護對話框
    不提供編輯 defaults。"""
    defaults = get_defaults()
    chains_out = []
    for it in items:
        entry: dict = {
            "chain_id": it["chain_id"],
            "name": it["name"],
            "downstream_leaders": it["downstream_leaders"],
        }
        if it.get("lead_lag_window_days"):
            entry["lead_lag_window_days"] = it["lead_lag_window_days"]
        if it.get("extraction_hint"):
            entry["extraction_hint"] = it["extraction_hint"]
        if it.get("note"):
            entry["note"] = it["note"]
        chains_out.append(entry)

    doc = {"defaults": defaults, "chains": chains_out}
    body = yaml.dump(doc, Dumper=_IndentDumper, allow_unicode=True, sort_keys=False, default_flow_style=None)

    os.makedirs(os.path.dirname(CHAINS_YAML_PATH), exist_ok=True)
    with open(CHAINS_YAML_PATH, "w", encoding="utf-8") as f:
        f.write(_FILE_HEADER + "\n" + body)
