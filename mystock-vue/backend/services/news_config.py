"""news_sources.yaml 載入器（docs/16.AI技術分析/Phase4-輕量化新聞輿情與總經監控.md §2，ADR-P4-01）。

每次呼叫都重新解析檔案，改設定不需重啟服務。與 strategies/config_loader.py 的一處刻意
差異：那裡解析失敗時回傳「空設定」（策略引擎的語意是「沒有策略」也能正常運作，掃描器對
空清單本來就會優雅跳過）；這裡解析失敗時**沿用上一次成功載入的設定**（§2 明文要求），因為
「來源清單突然變空」會讓爬蟲把所有既有資料在情緒計算時全部排除，等同於一次網路or打字失誤
就讓當天的降噪效果整個失控，比「維持舊設定直到下次修好」更危險。
"""
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml

from config import get_news_sources_config_path

logger = logging.getLogger("mystock-backend")


@dataclass
class NewsSourceDef:
    id: str
    name: str
    kind: str                      # "news"（進情緒評分）或 "buzz"（只計討論量）
    enabled: bool
    weight: float = 1.0
    endpoint: str = ""
    rate_limit_seconds: List[float] = field(default_factory=lambda: [3, 5])


@dataclass
class NewsSourcesConfig:
    dedup_window_hours: int = 48
    dedup_hamming_max: int = 3
    sentiment_window_days: int = 5
    sources: List[NewsSourceDef] = field(default_factory=list)

    def enabled_sources(self, kind: Optional[str] = None) -> List[NewsSourceDef]:
        return [s for s in self.sources if s.enabled and (kind is None or s.kind == kind)]

    def get(self, source_id: str) -> Optional[NewsSourceDef]:
        return next((s for s in self.sources if s.id == source_id), None)


_lock = threading.Lock()
_last_good: Optional[NewsSourcesConfig] = None


def _parse(raw: Dict[str, Any]) -> NewsSourcesConfig:
    defaults = raw.get("defaults") or {}
    sources = [
        NewsSourceDef(
            id=s["id"],
            name=s.get("name", s["id"]),
            kind=s.get("kind", "news"),
            enabled=bool(s.get("enabled", True)),
            weight=float(s.get("weight", 1.0)),
            endpoint=s.get("endpoint", ""),
            rate_limit_seconds=list(s.get("rate_limit_seconds", [3, 5])),
        )
        for s in raw.get("sources", [])
    ]
    return NewsSourcesConfig(
        dedup_window_hours=int(defaults.get("dedup_window_hours", 48)),
        dedup_hamming_max=int(defaults.get("dedup_hamming_max", 3)),
        sentiment_window_days=int(defaults.get("sentiment_window_days", 5)),
        sources=sources,
    )


def load_news_sources_config() -> NewsSourcesConfig:
    """重新解析 news_sources.yaml；失敗時記警告並沿用上一次成功載入的設定（§2）。
    程式啟動後第一次呼叫若立即失敗（尚無「上一次」可沿用），回傳空設定並記錄，
    比照 strategies/config_loader.py 對「檔案不存在」情境的處理方式。"""
    global _last_good
    path = get_news_sources_config_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        parsed = _parse(raw)
    except FileNotFoundError:
        logger.warning(f"[news_config] 找不到來源設定檔 {path}")
        with _lock:
            return _last_good if _last_good is not None else NewsSourcesConfig()
    except (yaml.YAMLError, KeyError, ValueError, TypeError) as e:
        logger.warning(f"[news_config] 來源設定檔格式錯誤 {path}: {e}，沿用上一次成功載入的設定")
        with _lock:
            return _last_good if _last_good is not None else NewsSourcesConfig()

    with _lock:
        _last_good = parsed
    return parsed
