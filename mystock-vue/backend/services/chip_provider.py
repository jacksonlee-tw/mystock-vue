"""策略引擎的唯一資料存取入口（策略管理架構 設計文件第 2 節「資料存取抽象化」）。

不重新實作 JSON/Postgres 雙讀取邏輯 —— DATA_SOURCE 切換已經在 services/stock_service.py 的
load_stock_data() / aggregate_stock_data() 做掉了，這裡只是包一層，把資料組成策略層要用的
ScanContext（含預先算好的 MA/BIAS），讓 strategies/ 底下的模組完全不需要認識 JSON 或 SQL
（策略管理架構 設計文件第 9 節「依賴隔離」鐵則）。
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from indicators.moving_average import bias_series, sma
from services.mops_fetcher import load_stock_revenue
from services.stock_service import aggregate_stock_data, load_stock_data

# 抓歷史資料的上限（月）。目前系統實際累積的資料量遠低於此，等同於「抓全部歷史」；
# 之所以不用 None／不限制，是沿用 aggregate_stock_data() 既有的 months 參數介面。
_MAX_HISTORY_MONTHS = 60


@dataclass
class ScanContext:
    symbol: str
    market: str
    name: str
    dates: List[str]
    opens: List[Optional[float]]
    highs: List[Optional[float]]
    lows: List[Optional[float]]
    closes: List[Optional[float]]
    volumes: List[Optional[float]]
    raw_records: List[Dict[str, Any]]
    ma: Dict[int, List[Optional[float]]] = field(default_factory=dict)
    bias: Dict[int, List[Optional[float]]] = field(default_factory=dict)
    volume_ma: List[Optional[float]] = field(default_factory=list)
    # MOPS 月營收（賣股策略 設計文件第四節「成長動能衰竭」），key 為 "YYYY-MM"，值為
    # services/mops_fetcher.py 落檔的原始記錄（含 yoy_percent）。僅台股有資料，美股恆為空 dict
    # （見 mops_fetcher.py 僅支援 market="tw"），conditions_fund.py 據此判斷是否要跳過。
    revenue: Dict[str, dict] = field(default_factory=dict)

    @property
    def length(self) -> int:
        return len(self.dates)


def _clean(value: Any) -> Optional[float]:
    """0 代表「當天沒回補到行情」（見 stock_service.get_stock_chart_payload 的既有處理），
    一律視為缺值，避免均線被拉去撞 0。"""
    if value is None or value == 0:
        return None
    return float(value)


class ChipDataProvider:
    """策略管理架構 設計文件第 6 節所稱的 ChipDataProvider 介面實作。"""

    async def get_bars(
        self,
        symbol: str,
        market: str,
        ma_periods: List[int],
        volume_ma_period: int = 5,
    ) -> Optional[ScanContext]:
        raw = await load_stock_data(symbol, market)
        if not raw:
            return None

        records = aggregate_stock_data(raw, period="daily", months=_MAX_HISTORY_MONTHS)
        if len(records) < 2:
            return None

        dates = [r["date"] for r in records]
        closes = [_clean(r.get("close")) for r in records]
        opens = [_clean(r.get("open")) for r in records]
        highs = [_clean(r.get("high")) for r in records]
        lows = [_clean(r.get("low")) for r in records]
        volumes = [r.get("volume") or None for r in records]

        name = next((r.get("name") for r in reversed(records) if r.get("name")), symbol)

        ma = {p: sma(closes, p) for p in ma_periods}
        bias = {p: bias_series(closes, ma[p]) for p in ma_periods}
        volume_ma = sma(volumes, volume_ma_period)

        # 月營收是 JSON-only 資料源（尚無 Postgres 表，見 docs/3.爬蟲開發 待辦清單），
        # 與 DATA_SOURCE 無關，一律直接讀檔；讀取失敗（檔案不存在）回傳空 dict，
        # 讓 conditions_fund.py 的資料充足度檢查自然跳過，不特別處理例外。
        revenue = load_stock_revenue(symbol) if market == "tw" else {}

        return ScanContext(
            symbol=symbol,
            market=market,
            name=name,
            dates=dates,
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=volumes,
            raw_records=records,
            ma=ma,
            bias=bias,
            volume_ma=volume_ma,
            revenue=revenue,
        )
