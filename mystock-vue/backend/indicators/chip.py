"""籌碼衍生指標（籌碼選股策略 設計文件第 3.2 節）。

比照 indicators/moving_average.py 的角色：所有籌碼相關的加減乘除集中在這裡，
strategies/conditions_chip.py 只呼叫、不重算（策略管理架構 設計文件第 9 節鐵則）。
目前只實作型態警示三策略（底部換手/高檔軋空/高檔出貨）需要的子集；核心策略
（外資大型權值波段/投信中小型作帳）需要的其餘指標留到 universe 模組完成後再補上。

輸入一律是 services/chip_provider.py 的 ScanContext.raw_records（單日一筆 dict 的清單，
已經是 aggregate_stock_data() 聚合過的日頻記錄）。讀值一律用 `.get(field, 0) or 0`——
T86/MI_MARGN 每個交易日都會落檔，0 是「當天淨買賣超為 0」的合法值，不是缺值；
真正的缺值是「回看視窗筆數不足」（idx 往前不夠 window 天），一律回傳 None，
呼叫端（conditions_chip.py）比照均線策略跳過該筆判斷，不得以 0 代入（設計文件第 3.3 節）。
"""
from typing import Callable, List, Optional

Records = List[dict]
ValueFn = Callable[[Records, int], Optional[float]]


def field_value(field: str) -> ValueFn:
    """回傳一個讀取指定欄位的 value_fn，缺值視為 0（見上方模組說明）。"""
    def _fn(records: Records, idx: int) -> float:
        return records[idx].get(field, 0) or 0
    return _fn


def _window(records: Records, idx: int, window: int, value_fn: ValueFn) -> Optional[List[float]]:
    start = idx - window + 1
    if start < 0:
        return None
    return [value_fn(records, j) for j in range(start, idx + 1)]


def cum_net(records: Records, field: str, idx: int, window: int) -> Optional[float]:
    """近 window 日（含當日）累計淨買賣超。"""
    values = _window(records, idx, window, field_value(field))
    return sum(values) if values is not None else None


def net_buy_days(records: Records, field: str, idx: int, window: int) -> Optional[int]:
    """近 window 日中淨買超（值 > 0）的天數。"""
    values = _window(records, idx, window, field_value(field))
    return sum(1 for v in values if v > 0) if values is not None else None


def consec_net_buy(records: Records, field: str, idx: int) -> int:
    """至今連續淨買超天數（從 idx 往回數，中斷即停）。"""
    fn = field_value(field)
    count, j = 0, idx
    while j >= 0 and fn(records, j) > 0:
        count += 1
        j -= 1
    return count


def consec_net_sell(records: Records, field: str, idx: int) -> int:
    """至今連續淨賣超天數（從 idx 往回數，中斷即停）。"""
    fn = field_value(field)
    count, j = 0, idx
    while j >= 0 and fn(records, j) < 0:
        count += 1
        j -= 1
    return count


def change_pct(records: Records, field: str, idx: int, window: int) -> Optional[float]:
    """(值[t] − 值[t-window]) / |值[t-window]| × 100。分母為 0 或視窗不足回傳 None。"""
    start = idx - window
    if start < 0:
        return None
    fn = field_value(field)
    prev, now = fn(records, start), fn(records, idx)
    if not prev:
        return None
    return (now - prev) / abs(prev) * 100


def rolling_max(records: Records, field: str, idx: int, window: int) -> Optional[float]:
    """近 window 日（含當日）最大值。"""
    values = _window(records, idx, window, field_value(field))
    return max(values) if values else None


def short_margin_ratio(records: Records, idx: int) -> Optional[float]:
    """券資比：融券餘額 / 融資餘額 × 100，融資餘額為 0（或缺值）回傳 None。"""
    margin = records[idx].get("margin_balance") or 0
    short = records[idx].get("short_balance") or 0
    if not margin:
        return None
    return short / margin * 100


def rolling_percentile(
    records: Records,
    idx: int,
    window: int,
    percentile: float,
    value_fn: ValueFn = short_margin_ratio,
) -> Optional[float]:
    """value_fn 在近 window 日（含當日）的第 percentile 百分位（線性內插）。
    預設對 short_margin_ratio 取值，用來算「券資比近 60 日第 90 百分位」這類相對門檻
    （籌碼選股策略 設計文件第 5.5 節 C3b），而不是對原始欄位本身取百分位。"""
    values = _window(records, idx, window, value_fn)
    if values is None:
        return None
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    pos = (percentile / 100) * (len(values) - 1)
    lo, hi = int(pos), min(int(pos) + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def net_buy_volume_ratio(records: Records, field: str, idx: int, window: int) -> Optional[float]:
    """累計指定法人淨買超佔同期總成交量的百分比（%）（選股功能與爬蟲 規格書 §5.4）。
    raw_records 的法人欄位單位為張（lots），成交量 volume 為股（shares），
    在此統一換算為股後計算比率：(累計張數 × 1000) / 累計成交股數 × 100。
    若成交量為 0 或視窗不足回傳 None。
    """
    values = _window(records, idx, window, field_value(field))
    vol_values = _window(records, idx, window, field_value("volume"))
    if values is None or vol_values is None:
        return None
    tot_vol = sum(vol_values)
    if tot_vol <= 0:
        return None
    tot_net_shares = sum(values) * 1000.0
    return (tot_net_shares / tot_vol) * 100.0

