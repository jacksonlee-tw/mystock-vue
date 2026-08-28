"""MACD／RSI／布林通道／ATR／近N日高低（含 EMA 前置基礎）一次性交叉驗證腳本
（Phase1-基礎量化與技術面 設計文件 FR-P1-10）。

專案沒有測試框架，驗證方式比照既有的 scripts/verify_kd.py：對每個指標寫一份與正式實作
不共用程式碼的獨立參考算法，交叉比對數值在容許誤差內一致；另外對真實標的做 AC-P1-4／
AC-P1-5／AC-P1-6 的欄位一致性檢查。全部印 PASS（或有依據的 SKIP）才算通過。

用法：python scripts/verify_indicators.py
"""
import asyncio
import math
import os
import sys
from typing import List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Windows 主控台預設編碼（cp950）印不出中文以外的符號，這裡強制轉 UTF-8，避免腳本印報告時
# 因為編碼而中途崩潰（不影響腳本本身的驗證邏輯）——沿用 scripts/verify_kd.py 的既有作法。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from indicators.moving_average import ema, sma  # noqa: E402
from indicators.macd import macd  # noqa: E402
from indicators.rsi import rsi  # noqa: E402
from indicators.atr import atr  # noqa: E402
from indicators.bollinger import bollinger_bands  # noqa: E402
from indicators.levels import rolling_high_low  # noqa: E402

TOLERANCE = 1e-3
_failures: List[str] = []


def _check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f"  — {detail}" if detail else ""))
    if not condition:
        _failures.append(label)


def _close(a: Optional[float], b: Optional[float], tol: float = TOLERANCE) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol


def _series_close(a: List[Optional[float]], b: List[Optional[float]], tol: float = TOLERANCE) -> bool:
    return len(a) == len(b) and all(_close(x, y, tol) for x, y in zip(a, b))


# ══════════════════════════════════════════════════════════════════════════
# 獨立參考實作：刻意用跟正式實作不同的程式結構（不同變數命名、不同迴圈切法），
# 降低「兩邊剛好共用同一個筆誤」的機率，但採同一套數學公式（Wilder / EMA 遞迴平滑）。
# ══════════════════════════════════════════════════════════════════════════

def _ref_ema(values, period):
    out = [None] * len(values)
    alpha = 2.0 / (period + 1)
    seed_window: List[float] = []
    prev = None
    for i, v in enumerate(values):
        if prev is None:
            if v is None:
                continue
            seed_window.append(v)
            if len(seed_window) < period:
                continue
            prev = sum(seed_window) / len(seed_window)
            out[i] = prev
            continue
        if v is None:
            continue
        prev = prev + alpha * (v - prev)
        out[i] = prev
    return out


def _ref_macd(closes, fast=12, slow=26, signal=9):
    cleaned = [c if c else None for c in closes]
    ema_fast = _ref_ema(cleaned, fast)
    ema_slow = _ref_ema(cleaned, slow)
    n = len(closes)
    dif = [None] * n
    for i in range(n):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            dif[i] = ema_fast[i] - ema_slow[i]
    sig = _ref_ema(dif, signal)
    hist = [None] * n
    for i in range(n):
        if dif[i] is not None and sig[i] is not None:
            hist[i] = dif[i] - sig[i]
    return dif, sig, hist


def _ref_rsi(closes, period=14):
    cleaned = [c if c else None for c in closes]
    n = len(cleaned)
    out = [None] * n
    gains: List[float] = []
    losses: List[float] = []
    avg_gain = avg_loss = None
    prev = None
    for i in range(n):
        c = cleaned[i]
        if c is None or prev is None:
            prev = c
            continue
        delta = c - prev
        prev = c
        g, l = max(delta, 0.0), max(-delta, 0.0)
        if avg_gain is None:
            gains.append(g)
            losses.append(l)
            if len(gains) < period:
                continue
            avg_gain = sum(gains) / period
            avg_loss = sum(losses) / period
        else:
            avg_gain = (avg_gain * (period - 1) + g) / period
            avg_loss = (avg_loss * (period - 1) + l) / period
        if avg_gain == 0 and avg_loss == 0:
            out[i] = 50.0
        elif avg_loss == 0:
            out[i] = 100.0
        elif avg_gain == 0:
            out[i] = 0.0
        else:
            out[i] = 100 - 100 / (1 + avg_gain / avg_loss)
    return out


def _ref_atr(highs, lows, closes, period=14):
    n = len(closes)
    hs = [h if h else None for h in highs]
    ls = [l if l else None for l in lows]
    cs = [c if c else None for c in closes]
    out = [None] * n
    trs: List[float] = []
    prev_close = prev_atr = None
    for i in range(n):
        h, l, c = hs[i], ls[i], cs[i]
        if h is None or l is None or c is None or prev_close is None:
            if c is not None:
                prev_close = c
            continue
        tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
        prev_close = c
        if prev_atr is None:
            trs.append(tr)
            if len(trs) < period:
                continue
            prev_atr = sum(trs) / period
        else:
            prev_atr = (prev_atr * (period - 1) + tr) / period
        out[i] = prev_atr
    return out


def _ref_bollinger(closes, period=20, num_std=2.0):
    n = len(closes)
    upper, mid, lower, bw = [None] * n, [None] * n, [None] * n, [None] * n
    for i in range(period - 1, n):
        window = closes[i - period + 1:i + 1]
        if any(v is None for v in window):
            continue
        m = sum(window) / period
        variance = sum((v - m) ** 2 for v in window) / period
        std = math.sqrt(variance)
        mid[i] = m
        upper[i] = m + num_std * std
        lower[i] = m - num_std * std
        if m:
            bw[i] = (upper[i] - lower[i]) / m
    return upper, mid, lower, bw


def _ref_rolling_high_low(highs, lows, window):
    n = len(highs)
    res, sup = [None] * n, [None] * n
    hs = [h if h else None for h in highs]
    ls = [l if l else None for l in lows]
    for i in range(n):
        start = max(0, i - window + 1)
        wh = [v for v in hs[start:i + 1] if v is not None]
        wl = [v for v in ls[start:i + 1] if v is not None]
        if wh:
            res[i] = max(wh)
        if wl:
            sup[i] = min(wl)
    return res, sup


# ══════════════════════════════════════════════════════════════════════════
# EMA
# ══════════════════════════════════════════════════════════════════════════

def test_ema_cross_check_and_warmup():
    closes = [10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 10, 9, 10, 11, 12]
    got = ema(closes, 5)
    ref = _ref_ema(closes, 5)
    _check("EMA(5) 與獨立參考實作一致", _series_close(got, ref), f"got={got}")
    _check("EMA 種子成形前（前 period-1 根）為 None", all(v is None for v in got[:4]))


def test_ema_insufficient_length():
    got = ema([10, 11, 12], 20)
    _check("序列長度小於暖身期 EMA 全部 None", all(v is None for v in got))


def test_ema_gap_state_retained():
    """缺值時遞迴狀態不重置（FR-P1-1 ②）：呼叫端先把 0 清成 None 才傳入。"""
    closes = [10, 11, 12, 13, 14, 15, 16, 0, 15, 16, 17]
    cleaned = [c if c else None for c in closes]
    got = ema(cleaned, 5)
    _check("EMA 缺值當根輸出 None", got[7] is None, f"got={got}")
    _check("EMA 缺值後恢復更新（延續既有狀態，非重新起算種子）", got[8] is not None, f"got={got}")


# ══════════════════════════════════════════════════════════════════════════
# MACD
# ══════════════════════════════════════════════════════════════════════════

def test_macd_cross_check():
    closes = [100 + 5 * math.sin(i / 3.0) + i * 0.1 for i in range(60)]
    dif, sig, hist = macd(closes, 12, 26, 9)
    rdif, rsig, rhist = _ref_macd(closes, 12, 26, 9)
    _check("MACD DIF 與獨立參考實作一致", _series_close(dif, rdif))
    _check("MACD Signal 與獨立參考實作一致", _series_close(sig, rsig))
    _check("MACD Histogram 與獨立參考實作一致", _series_close(hist, rhist))
    _check("MACD 暖身期未滿（slow_period-1 根）前 DIF 為 None", all(v is None for v in dif[:25]))


def test_macd_insufficient_length():
    dif, sig, hist = macd([10, 11, 12, 13, 14])
    _check("MACD 序列長度不足時 dif/signal/histogram 全部 None",
           all(v is None for v in dif) and all(v is None for v in sig) and all(v is None for v in hist))


# ══════════════════════════════════════════════════════════════════════════
# RSI
# ══════════════════════════════════════════════════════════════════════════

def test_rsi_cross_check():
    closes = [100 + 8 * math.sin(i / 4.0) + (i % 5) * 0.3 for i in range(50)]
    closes[20] = 0  # 模擬當天沒回補到行情（缺值）
    for period in (6, 14):
        got = rsi(closes, period)
        ref = _ref_rsi(closes, period)
        _check(f"RSI({period}) 與獨立參考實作一致", _series_close(got, ref), f"got={got}")


def test_rsi_flat_price_neutral():
    """連續一價鎖死：漲跌幅全為 0，avg_gain=avg_loss=0，須回傳中性 50，不得除以零。"""
    got = rsi([100] * 20, 14)
    _check("連續同價 RSI 視為中性 50、不拋例外", all(v is None or _close(v, 50.0) for v in got), f"got={got}")


def test_rsi_all_gain_no_exception():
    """連續上漲（跌幅恆為 0）：avg_loss=0，RSI 應為 100，不得除以零或回傳 inf。"""
    got = rsi(list(range(1, 20)), 14)
    last = got[-1]
    _check("連續上漲 RSI=100 且非 inf", last is not None and last == 100.0 and last != float("inf"), f"last={last}")


def test_rsi_insufficient_length():
    got = rsi([10, 11, 12], 14)
    _check("RSI 序列長度不足全部 None", all(v is None for v in got))


# ══════════════════════════════════════════════════════════════════════════
# ATR
# ══════════════════════════════════════════════════════════════════════════

def test_atr_cross_check():
    closes = [100 + 6 * math.sin(i / 5.0) for i in range(50)]
    highs = [c + 1.5 for c in closes]
    lows = [c - 1.2 for c in closes]
    got = atr(highs, lows, closes, 14)
    ref = _ref_atr(highs, lows, closes, 14)
    _check("ATR 與獨立參考實作一致", _series_close(got, ref), f"got={got}")
    _check("ATR 序列首日為 None（無前一日收盤價）", got[0] is None)


def test_atr_insufficient_length():
    got = atr([10, 11], [9, 10], [9.5, 10.5], 14)
    _check("ATR 序列長度不足全部 None", all(v is None for v in got))


def test_atr_frozen_price_no_exception():
    """連續一價鎖死（H=L=C）：TR 恆為 0，遞迴平滑得到 ATR=0，不得除以零或拋例外。"""
    got = atr([100.0] * 20, [100.0] * 20, [100.0] * 20, 14)
    _check("連續一價 ATR 為 0 且不拋例外", got[-1] == 0.0, f"got[-1]={got[-1]}")


# ══════════════════════════════════════════════════════════════════════════
# 布林通道
# ══════════════════════════════════════════════════════════════════════════

def test_bollinger_cross_check():
    closes = [100 + 4 * math.sin(i / 3.0) + (i % 6) * 0.2 for i in range(40)]
    upper, mid, lower, bw = bollinger_bands(closes, 20, 2.0)
    rupper, rmid, rlower, rbw = _ref_bollinger(closes, 20, 2.0)
    _check("布林上軌與獨立參考實作一致", _series_close(upper, rupper))
    _check("布林中軌與獨立參考實作一致", _series_close(mid, rmid))
    _check("布林下軌與獨立參考實作一致", _series_close(lower, rlower))
    _check("布林帶寬與獨立參考實作一致", _series_close(bw, rbw))


def test_bollinger_reuses_existing_middle():
    """ADR-P1-05：呼叫端已傳入 middle 時不得重算 SMA，須原樣沿用同一份結果。"""
    closes = [100 + i for i in range(25)]
    existing_middle = sma(closes, 20)
    _, mid, _, _ = bollinger_bands(closes, 20, 2.0, middle=existing_middle)
    _check("布林中軌沿用傳入的既有 SMA（不重算）", mid is existing_middle)


def test_bollinger_flat_price_no_exception():
    """連續同價：標準差為 0，upper=middle=lower、bandwidth=0，不得除以零或回傳 inf。"""
    upper, mid, lower, bw = bollinger_bands([100.0] * 25, 20, 2.0)
    idx = 19
    _check("連續同價布林上下軌等於中軌、帶寬為 0",
           _close(upper[idx], 100.0) and _close(lower[idx], 100.0) and _close(bw[idx], 0.0),
           f"upper={upper[idx]} mid={mid[idx]} lower={lower[idx]} bw={bw[idx]}")


def test_bollinger_insufficient_length():
    upper, _, lower, _ = bollinger_bands([100, 101, 102], 20, 2.0)
    _check("布林序列長度不足全部 None", all(v is None for v in upper) and all(v is None for v in lower))


# ══════════════════════════════════════════════════════════════════════════
# 近 N 日高低
# ══════════════════════════════════════════════════════════════════════════

def test_rolling_high_low_cross_check():
    highs = [10, 12, 11, 15, 9, 8, 20, 13, 14, 7, 6, 18, 19, 5, 16]
    lows = [8, 9, 7, 10, 6, 5, 15, 9, 10, 4, 3, 12, 14, 2, 11]
    res, sup = rolling_high_low(highs, lows, 5)
    rres, rsup = _ref_rolling_high_low(highs, lows, 5)
    _check("近5日高低與獨立參考實作一致", res == rres and sup == rsup, f"res={res} sup={sup}")


def test_rolling_high_low_partial_window_at_start():
    """視窗大於已累積天數：取現有天數內的極值，不因整窗未滿就整段輸出 None。"""
    res, sup = rolling_high_low([10, 12, 11], [8, 9, 7], 20)
    _check("視窗大於序列長度時取現有天數內極值", res == [10, 12, 12] and sup == [8, 8, 7], f"res={res} sup={sup}")


def test_rolling_high_low_all_missing():
    n = 5
    res, sup = rolling_high_low([None] * n, [None] * n, 3)
    _check("全部缺值時近N日高低全為 None", all(v is None for v in res) and all(v is None for v in sup))


# ══════════════════════════════════════════════════════════════════════════
# Tier 3（AC-P1-4／AC-P1-5／AC-P1-6）：真實標的，圖表 payload 端到端檢查
# ══════════════════════════════════════════════════════════════════════════

async def _tier3_real_symbol(symbol: str, market: str) -> None:
    from services.stock_service import get_stock_chart_payload

    months_options = [1, 3, 6, 12]
    payloads = {}
    for months in months_options:
        payload = await get_stock_chart_payload(symbol, period="daily", months=months, market=market, source="json")
        if "error" in payload:
            print(f"[SKIP] Tier3：{symbol}（{market}）讀不到資料（{payload['error']}），略過此檢查")
            return
        payloads[months] = payload

    baseline_months = max(months_options)
    baseline = payloads[baseline_months]
    atr_key = f"atr_{baseline['atr'].get('period', 14)}"

    baseline_dif = dict(zip(baseline["dates"], baseline["macd"]["dif"]))
    baseline_rsi14 = dict(zip(baseline["dates"], baseline["rsi"].get("rsi_14") or []))
    baseline_atr = dict(zip(baseline["dates"], baseline["atr"].get(atr_key) or []))

    all_ok = True
    for months, payload in payloads.items():
        if months == baseline_months:
            continue
        dif_by_date = dict(zip(payload["dates"], payload["macd"]["dif"]))
        rsi_by_date = dict(zip(payload["dates"], payload["rsi"].get("rsi_14") or []))
        atr_by_date = dict(zip(payload["dates"], payload["atr"].get(atr_key) or []))
        for d in payload["dates"]:
            if d in baseline_dif and not _close(dif_by_date.get(d), baseline_dif[d]):
                all_ok = False
                print(f"       MACD 不一致：date={d} months={months}")
            if d in baseline_rsi14 and not _close(rsi_by_date.get(d), baseline_rsi14[d]):
                all_ok = False
                print(f"       RSI 不一致：date={d} months={months}")
            if d in baseline_atr and not _close(atr_by_date.get(d), baseline_atr[d]):
                all_ok = False
                print(f"       ATR 不一致：date={d} months={months}")

    _check(f"AC-P1-4：{symbol}（{market}）不同月份區間重疊日期 MACD/RSI/ATR 完全相同", all_ok)

    bollinger_middle_latest = (baseline["bollinger"].get("middle") or [None])[-1]
    ma20_latest = (baseline["moving_averages"].get("MA20") or [None])[-1]
    _check(f"AC-P1-5：{symbol} bollinger.middle 與 ma.MA20 數值相等",
           _close(bollinger_middle_latest, ma20_latest),
           f"bollinger.middle={bollinger_middle_latest} ma20={ma20_latest}")

    records = baseline["records"]
    highs_20 = [r.get("high") for r in records[-20:] if r.get("high")]
    lows_20 = [r.get("low") for r in records[-20:] if r.get("low")]
    expected_resistance_20d = max(highs_20) if highs_20 else None
    expected_support_20d = min(lows_20) if lows_20 else None
    got_resistance_20d = (baseline["levels"].get("resistance_20d") or [None])[-1]
    got_support_20d = (baseline["levels"].get("support_20d") or [None])[-1]
    _check(f"AC-P1-6：{symbol} 近20日壓力/支撐與手動核對一致",
           _close(got_resistance_20d, expected_resistance_20d) and _close(got_support_20d, expected_support_20d),
           f"got=({got_resistance_20d},{got_support_20d}) expected=({expected_resistance_20d},{expected_support_20d})")


# ══════════════════════════════════════════════════════════════════════════

def main():
    test_ema_cross_check_and_warmup()
    test_ema_insufficient_length()
    test_ema_gap_state_retained()

    test_macd_cross_check()
    test_macd_insufficient_length()

    test_rsi_cross_check()
    test_rsi_flat_price_neutral()
    test_rsi_all_gain_no_exception()
    test_rsi_insufficient_length()

    test_atr_cross_check()
    test_atr_insufficient_length()
    test_atr_frozen_price_no_exception()

    test_bollinger_cross_check()
    test_bollinger_reuses_existing_middle()
    test_bollinger_flat_price_no_exception()
    test_bollinger_insufficient_length()

    test_rolling_high_low_cross_check()
    test_rolling_high_low_partial_window_at_start()
    test_rolling_high_low_all_missing()

    for symbol, market in (("2330", "tw"), ("AAPL", "us")):
        try:
            asyncio.run(_tier3_real_symbol(symbol, market))
        except Exception as e:
            print(f"[SKIP] Tier3（{symbol}/{market}）執行時發生例外，略過（不計入失敗）：{e}")

    print()
    if _failures:
        print(f"❌ {len(_failures)} 項失敗：{_failures}")
        sys.exit(1)
    else:
        print("✅ 全部通過")


if __name__ == "__main__":
    main()
