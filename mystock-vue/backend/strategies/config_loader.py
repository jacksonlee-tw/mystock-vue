"""策略設定檔（YAML）載入器（策略管理架構 設計文件第 6 節 Registry / 均線策略警示系統 設計文件第 7 節）。

每次呼叫都重新解析檔案 ── 檔案很小、掃描頻率是「每日一次」等級，不需要快取，
這樣改 YAML 立即生效，不用重啟服務（滿足均線策略警示系統 設計文件 AC-7）。
檔案不存在或格式錯誤時記警告、回傳空設定，不讓服務掛掉。
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml

from config import get_strategy_config_path

logger = logging.getLogger("mystock-backend")

# §6.4（Phase4-輕量化新聞輿情與總經監控.md，v2.8 更新）：sentiment_filter／macro_filter
# 屬於「持續性狀態」（大盤站上月線可能連續成立數十天），不是轉折事件。v2.8 新增 `gates`
# 欄位（見 StrategyDef.gates／strategies/scanner.py 的 _evaluate_gates()）後，正確用法是
# 把這兩型放進 `gates:`，不是放進 `conditions:`——但 YAML 沒有 schema 強制，仍可能誤放，
# 下面兩條檢核都併入既有 YAML 載入批次，不另立檢查函式（見規格書 §15.4 對此落差點的說明）：
#   1. `conditions` 只掛閘門型（沒有真正的主觸發，見下方迴圈）
#   2. `gates` 有設定但 `conditions` 是空的（gates 永遠不會被評估到，整條策略形同沒作用）
_GATE_ONLY_CONDITION_TYPES = {"sentiment_filter", "macro_filter"}


@dataclass
class StrategyDef:
    id: str
    name: str
    category: str
    enabled: bool
    markets: List[str]
    description: str = ""
    conditions: List[dict] = field(default_factory=list)
    # §6.1 AND 閘門機制（v2.8 新增）：全部通過，conditions 觸發的候選警示才會真的放行；
    # 本身不獨立產生警示（與 conditions 的本質差異，見 strategies/scanner.py 的
    # _evaluate_gates() 說明）。語意上屬於 condition（會決定訊號成立與否），跟只加分不擋的
    # filters 完全不同角色，型別沿用既有 CONDITION_REGISTRY，不另立一套註冊表。
    gates: List[dict] = field(default_factory=list)
    filters: List[dict] = field(default_factory=list)
    cooldown_days: Optional[int] = None
    # ── 選股與風控延伸欄位（選股功能與爬蟲 規格書 §7、§13）───────────
    scope: str = "watchlist"  # "watchlist" 或 "universe"
    max_picks_per_day: Optional[int] = None
    sort_by: Optional[str] = None
    universe_tier: Optional[str] = None


@dataclass
class StrategyConfig:
    defaults: Dict[str, Any] = field(default_factory=dict)
    strategies: List[StrategyDef] = field(default_factory=list)
    filters_registry: List[dict] = field(default_factory=list)

    def enabled_for_market(self, market: str) -> List[StrategyDef]:
        return [s for s in self.strategies if s.enabled and market in s.markets]

    def get(self, strategy_id: str) -> StrategyDef | None:
        return next((s for s in self.strategies if s.id == strategy_id), None)


def load_strategy_config() -> StrategyConfig:
    path = get_strategy_config_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning(f"[策略引擎] 找不到策略設定檔 {path}，本次視為沒有任何策略")
        return StrategyConfig()
    except yaml.YAMLError as e:
        logger.warning(f"[策略引擎] 策略設定檔格式錯誤 {path}: {e}")
        return StrategyConfig()

    strategies = [
        StrategyDef(
            id=s["id"],
            name=s.get("name", s["id"]),
            category=s.get("category", "technical"),
            enabled=s.get("enabled", True),
            markets=s.get("markets", ["tw", "us"]),
            description=s.get("description", ""),
            conditions=s.get("conditions", []),
            gates=s.get("gates", []),
            filters=s.get("filters", []),
            cooldown_days=s.get("cooldown_days"),
            scope=s.get("scope", "watchlist"),
            max_picks_per_day=s.get("max_picks_per_day"),
            sort_by=s.get("sort_by"),
            universe_tier=s.get("universe_tier"),
        )
        for s in raw.get("strategies", [])
    ]

    for s in strategies:
        if not s.enabled:
            continue
        condition_types = {c.get("type") for c in s.conditions if isinstance(c, dict)}
        if condition_types and condition_types.issubset(_GATE_ONLY_CONDITION_TYPES):
            logger.warning(
                f"[策略引擎] 策略 {s.id} 的 conditions 只掛了閘門型（{sorted(condition_types)}）、"
                f"沒有主觸發條件——閘門屬於持續性狀態（例如大盤站上月線可能連續成立數十天），"
                f"放在 conditions 裡沒有主觸發時每個交易日都會成立、天天推播（規格書 §6.4）；"
                f"若本意是當閘門用，應改放進 gates 欄位，不是 conditions"
            )
        if s.gates and not s.conditions:
            logger.warning(
                f"[策略引擎] 策略 {s.id} 設定了 gates（{sorted({g.get('type') for g in s.gates if isinstance(g, dict)})}）"
                f"但 conditions 是空的——gates 只在 conditions 觸發時才會被評估到，"
                f"沒有主觸發條件時這些 gates 永遠不會被檢查，整條策略形同沒作用（規格書 §6.4）"
            )

    return StrategyConfig(
        defaults=raw.get("defaults", {}),
        strategies=strategies,
        filters_registry=raw.get("filters_registry", []),
    )
