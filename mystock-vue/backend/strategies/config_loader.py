"""策略設定檔（YAML）載入器（策略管理架構 設計文件第 6 節 Registry / 均線策略警示系統 設計文件第 7 節）。

每次呼叫都重新解析檔案 ── 檔案很小、掃描頻率是「每日一次」等級，不需要快取，
這樣改 YAML 立即生效，不用重啟服務（滿足均線策略警示系統 設計文件 AC-7）。
檔案不存在或格式錯誤時記警告、回傳空設定，不讓服務掛掉。
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

import yaml

from config import get_strategy_config_path

logger = logging.getLogger("mystock-backend")


@dataclass
class StrategyDef:
    id: str
    name: str
    category: str
    enabled: bool
    markets: List[str]
    conditions: List[dict] = field(default_factory=list)
    filters: List[dict] = field(default_factory=list)


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
            conditions=s.get("conditions", []),
            filters=s.get("filters", []),
        )
        for s in raw.get("strategies", [])
    ]

    return StrategyConfig(
        defaults=raw.get("defaults", {}),
        strategies=strategies,
        filters_registry=raw.get("filters_registry", []),
    )
