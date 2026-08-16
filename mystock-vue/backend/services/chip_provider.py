"""策略引擎的唯一資料存取入口（策略管理架構 設計文件第 2 節「資料存取抽象化」、選股功能與爬蟲 規格書 §4）。

支援既有逐檔載入（Watchlist）與批次預載載入（MarketPreload，全市場選股掃描）。
組成策略層要用的 ScanContext（含 OHLC、MA、BIAS、KD、估值與月營收 Point-in-time 平行序列）。
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from config import MAX_HISTORY_MONTHS
from indicators.fundamental import latest_visible_month
from indicators.moving_average import bias_series, sma
from indicators.stochastic import compute_kd_set
from services.mops_fetcher import load_stock_revenue
from services.stock_service import aggregate_stock_data, load_stock_data


@dataclass
class KDSeries:
    """單一 KD 參數組（如 (9,3,3)）的 K/D 序列（KD指標 設計規格書 §4.1）。"""
    k: List[Optional[float]]
    d: List[Optional[float]]


@dataclass
class PositionContext:
    """持倉風控上下文（進出場策略整合，選股功能與爬蟲 規格書 §6.2）。"""
    symbol: str
    market: str
    shares: float
    avg_cost: float
    entry_date: str
    holding_trading_days: int
    peak_close_since_entry: float
    unrealized_return_pct: float


@dataclass
class MarketPreload:
    """批次預載數據結構（選股功能與爬蟲 規格書 §4.3）。"""
    quotes: Dict[str, List[dict]] = field(default_factory=dict)
    valuation: Dict[str, Dict[str, dict]] = field(default_factory=dict)
    revenue: Dict[str, Dict[str, dict]] = field(default_factory=dict)


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
    kd: Dict[Tuple[int, int, int], KDSeries] = field(default_factory=dict)
    revenue: Dict[str, dict] = field(default_factory=dict)
    # ── 估值與營收 Point-in-time 平行序列（選股功能與爬蟲 規格書 §4.1）──────────
    valuation: Dict[str, List[Optional[float]]] = field(default_factory=dict)
    revenue_visible_month: List[Optional[str]] = field(default_factory=list)
    revenue_yoy: List[Optional[float]] = field(default_factory=list)
    revenue_mom: List[Optional[float]] = field(default_factory=list)
    # 出場風控專用；僅 scan_positions() 入口會填，選股掃描為 None
    position: Optional[PositionContext] = None

    @property
    def length(self) -> int:
        return len(self.dates)


def _clean(value: Any) -> Optional[float]:
    """0 代表缺值，避免均線被拉去撞 0。"""
    if value is None or value == 0:
        return None
    return float(value)


class ChipDataProvider:
    """策略管理架構 ChipDataProvider 介面實作。"""

    async def get_bars(
        self,
        symbol: str,
        market: str,
        ma_periods: List[int],
        volume_ma_period: int = 5,
        kd_params: Optional[List[Tuple[int, int, int]]] = None,
        kd_warmup_bars: int = 25,
        kd_smoothing: str = "wilder_1_3",
        with_valuation: bool = False,
        preloaded: Optional[MarketPreload] = None,
        position: Optional[PositionContext] = None,
    ) -> Optional[ScanContext]:
        # 1. 取得原始歷史記錄 (從預載快取或既有 load_stock_data)
        if preloaded and symbol in preloaded.quotes:
            records = preloaded.quotes[symbol]
        else:
            raw = await load_stock_data(symbol, market)
            if not raw:
                return None
            records = aggregate_stock_data(raw, period="daily", months=MAX_HISTORY_MONTHS)

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

        # KD 指標計算
        kd_raw = compute_kd_set(highs, lows, closes, kd_params or [], warmup_bars=kd_warmup_bars, smoothing=kd_smoothing)
        kd = {params: KDSeries(k=k_series, d=d_series) for params, (k_series, d_series) in kd_raw.items()}

        # 月營收字典載入 (MOPS 既有或預載)
        if preloaded and symbol in preloaded.revenue:
            revenue_dict = preloaded.revenue[symbol]
        elif market == "tw":
            revenue_dict = load_stock_revenue(symbol)
        else:
            revenue_dict = {}

        # 估值與營收平行序列建構 (Point-in-time)
        val_series: Dict[str, List[Optional[float]]] = {
            "pe_ratio": [],
            "pb_ratio": [],
            "dividend_yield": [],
        }
        rev_visible_months: List[Optional[str]] = []
        rev_yoy_series: List[Optional[float]] = []
        rev_mom_series: List[Optional[float]] = []

        if with_valuation and market == "tw":
            val_lookup = (preloaded.valuation.get(symbol) if preloaded else None) or {}
            for d_str in dates:
                # 估值序列：該日有值填入，缺值留 None（不補 0、不沿用前一日，ADR-SP-08）
                v_entry = val_lookup.get(d_str, {})
                val_series["pe_ratio"].append(v_entry.get("pe_ratio"))
                val_series["pb_ratio"].append(v_entry.get("pb_ratio"))
                val_series["dividend_yield"].append(v_entry.get("dividend_yield"))

                # 營收序列：Point-in-time 可見性計算
                try:
                    t_date = date.fromisoformat(d_str)
                    vis_month = latest_visible_month(revenue_dict, t_date)
                    rev_visible_months.append(vis_month)
                    if vis_month and vis_month in revenue_dict:
                        rev_yoy_series.append(revenue_dict[vis_month].get("yoy_percent"))
                        rev_mom_series.append(revenue_dict[vis_month].get("mom_percent"))
                    else:
                        rev_yoy_series.append(None)
                        rev_mom_series.append(None)
                except Exception:
                    rev_visible_months.append(None)
                    rev_yoy_series.append(None)
                    rev_mom_series.append(None)

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
            revenue=revenue_dict,
            kd=kd,
            valuation=val_series,
            revenue_visible_month=rev_visible_months,
            revenue_yoy=rev_yoy_series,
            revenue_mom=rev_mom_series,
            position=position,
        )
