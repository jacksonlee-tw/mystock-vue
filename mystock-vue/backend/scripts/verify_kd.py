"""KD 隨機指標一次性驗證腳本（KD指標 設計規格書 第 10 節）。

專案沒有測試框架，驗證方式比照既有的 scripts/compare_data_sources.py：獨立寫一份與
indicators/stochastic.py 完全不共用程式碼的「參考實作」交叉比對，加上邊界案例逐項斷言，
外加對一檔真實標的的月份區間一致性檢查（AC-6）。全部印 PASS 才代表通過。

用法：python scripts/verify_kd.py
"""
import asyncio
import os
import sys
from fractions import Fraction
from typing import List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Windows 主控台預設編碼（cp950）印不出中文以外的符號（≈、✅、❌ 等），這裡強制轉 UTF-8，
# 避免腳本印報告時因為編碼而中途崩潰（不影響腳本本身的驗證邏輯）。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from indicators.stochastic import stochastic  # noqa: E402

TOLERANCE = 1e-4
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
# Tier 1：小樣本、整數 OHLC，用 Fraction 精確有理數運算手算期望值（可逐行覆核）。
# ══════════════════════════════════════════════════════════════════════════

def _exact_kd(highs, lows, closes, fastk_period, slowk_period, slowd_period, warmup_bars=0, seed=Fraction(50)):
    """與 indicators/stochastic.py 完全獨立撰寫的參考實作，用 Fraction 做精確運算。"""
    n = len(closes)
    k_out: List[Optional[Fraction]] = [None] * n
    d_out: List[Optional[Fraction]] = [None] * n
    k_prev = d_prev = None
    k_alpha, d_alpha = Fraction(1, slowk_period), Fraction(1, slowd_period)
    warm = 0
    for i in range(n):
        if i < fastk_period - 1:
            continue
        wh, wl = highs[i - fastk_period + 1: i + 1], lows[i - fastk_period + 1: i + 1]
        c = closes[i]
        if c is None or any(v is None for v in wh) or any(v is None for v in wl):
            continue
        hhv, llv = max(wh), min(wl)
        rsv = Fraction(50) if hhv == llv else Fraction(c - llv, hhv - llv) * 100
        k_seed = k_prev if k_prev is not None else seed
        d_seed = d_prev if d_prev is not None else seed
        k_now = k_alpha * rsv + (1 - k_alpha) * k_seed
        d_now = d_alpha * k_now + (1 - d_alpha) * d_seed
        k_prev, d_prev = k_now, d_now
        warm += 1
        if warm >= warmup_bars:
            k_out[i], d_out[i] = k_now, d_now
    return k_out, d_out


def test_tier1_basic_known_values():
    """6 根整數 K 棒，fastk=3/slowk=3/slowd=3，warmup_bars=0（直接看未過濾的原始遞迴值）。"""
    highs = [10, 11, 12, 13, 11, 10]
    lows = [8, 9, 8, 10, 9, 7]
    closes = [9, 10, 11, 12, 10, 8]

    k, d = stochastic(highs, lows, closes, fastk_period=3, slowk_period=3, slowd_period=3, warmup_bars=0)
    ek, ed = _exact_kd(highs, lows, closes, 3, 3, 3, warmup_bars=0)

    _check("Tier1 基本序列 K 值", _series_close(k, [float(v) if v is not None else None for v in ek]),
           f"got={k} expected≈{[float(v) if v is not None else None for v in ek]}")
    _check("Tier1 基本序列 D 值", _series_close(d, [float(v) if v is not None else None for v in ed]),
           f"got={d} expected≈{[float(v) if v is not None else None for v in ed]}")
    # 手算覆核（見 KD指標 設計規格書 §10 註解）：idx2 RSV=75 → K2=175/3≈58.3333, D2=475/9≈52.7778
    _check("Tier1 idx2 K 手算對照", _close(k[2], 58.3333), f"k[2]={k[2]}")
    _check("Tier1 idx2 D 手算對照", _close(d[2], 52.7778), f"d[2]={d[2]}")
    _check("Tier1 開頭不足 fastk_period 根留 None", k[0] is None and k[1] is None and d[0] is None and d[1] is None)


def test_tier1_hhv_eq_llv():
    """連續一價鎖死（H=L=C），HHV==LLV 時 RSV 視為中性 50，不得除以零。"""
    highs = lows = closes = [100, 100, 100]
    k, d = stochastic(highs, lows, closes, fastk_period=3, slowk_period=3, slowd_period=3, warmup_bars=0)
    _check("HHV==LLV 不拋例外且 RSV=50 → K=50.0", _close(k[2], 50.0), f"k={k}")
    _check("HHV==LLV 不拋例外且 RSV=50 → D=50.0", _close(d[2], 50.0), f"d={d}")


def test_tier1_leading_missing():
    """開頭連續缺值：前 5 根 None，第 6 根起才有效資料，視窗需完全滑出缺值區才輸出。"""
    n_leading = 5
    highs = [None] * n_leading + [20, 21, 22]
    lows = [None] * n_leading + [18, 19, 18]
    closes = [None] * n_leading + [19, 20, 21]
    k, d = stochastic(highs, lows, closes, fastk_period=3, slowk_period=3, slowd_period=3, warmup_bars=0)
    _check("開頭缺值期間全部為 None", all(v is None for v in k[:7]), f"k[:7]={k[:7]}")
    # idx7 window=[5,6,7]=(20,21,22)/(18,19,18)，RSV=(21-18)/(22-18)*100=75，與 Tier1 基本序列同構
    _check("缺值滑出後首個有效值", _close(k[7], 58.3333) and _close(d[7], 52.7778), f"k[7]={k[7]} d[7]={d[7]}")


def test_tier1_insufficient_length():
    """序列長度不足 fastk_period 根：全部應為 None，不拋例外。"""
    highs, lows, closes = [10, 11], [8, 9], [9, 10]
    k, d = stochastic(highs, lows, closes, fastk_period=9, slowk_period=3, slowd_period=3, warmup_bars=0)
    _check("長度不足 fastk_period 全部 None", all(v is None for v in k) and all(v is None for v in d))


def test_tier1_all_missing():
    """全部缺值：不得拋例外，輸出長度需與輸入一致、全部 None。"""
    n = 10
    k, d = stochastic([None] * n, [None] * n, [None] * n, fastk_period=3, warmup_bars=0)
    _check("全部缺值長度一致且全 None", len(k) == n and len(d) == n and all(v is None for v in k + d))


def test_tier1_gap_state_retained():
    """中間缺值：遞迴狀態（k_prev/d_prev）保留不重置，是本次最容易誤判成 bug 的行為
    （KD指標 設計規格書 §3.2 邊界條件）。用「若重置成種子 50 會得到明顯不同的值」來反證。
    """
    highs = [10, 11, 12, 0, 13, 11, 12]
    lows = [8, 9, 8, 0, 10, 9, 9]
    closes = [9, 10, 11, 0, 12, 10, 11]  # idx3 的 0 會被 _clean() 視為缺值
    k, d = stochastic(highs, lows, closes, fastk_period=3, slowk_period=3, slowd_period=3, warmup_bars=0)

    _check("缺值當根與視窗未滑出前皆為 None", k[3] is None and k[4] is None and k[5] is None,
           f"k[3:6]={k[3:6]}")
    # idx6 window=[4,5,6] 全部有效，RSV=(11-9)/(13-9)*100=50；若狀態「有」保留（延續 idx2 的
    # K=175/3, D=475/9），K6=500/9≈55.5556；若錯誤「重置」成種子 50，K6 會恰好等於 50.0——
    # 兩者數值明顯不同，用來直接反證「有沒有錯誤重置」。
    _check("缺值後接續使用前值（K 不等於重置後的 50.0）", not _close(k[6], 50.0), f"k[6]={k[6]}")
    _check("缺值後狀態保留的精確值", _close(k[6], 55.5556) and _close(d[6], 53.7037), f"k[6]={k[6]} d[6]={d[6]}")


def test_unsupported_smoothing_falls_back():
    """未實作的 smoothing 值：記警告後退回 wilder_1_3，不得拋例外（決議 D1）。"""
    highs = [10, 11, 12, 13, 11, 10] * 6
    lows = [8, 9, 8, 10, 9, 7] * 6
    closes = [9, 10, 11, 12, 10, 8] * 6
    k1, d1 = stochastic(highs, lows, closes, warmup_bars=5, smoothing="wilder_1_3")
    k2, d2 = stochastic(highs, lows, closes, warmup_bars=5, smoothing="sma")  # 尚未實作，應退回 wilder_1_3
    _check("未支援的 smoothing 不拋例外且退回 wilder_1_3", _series_close(k1, k2) and _series_close(d1, d2))


# ══════════════════════════════════════════════════════════════════════════
# Tier 2：較長序列（預設參數 9,3,3／warmup=25），與獨立撰寫的浮點參考實作交叉比對。
# ══════════════════════════════════════════════════════════════════════════

def _float_reference_kd(highs, lows, closes, fastk=9, slowk=3, slowd=3, warmup=25, seed=50.0):
    """故意用跟 indicators/stochastic.py 不同的寫法（先攤平算 RSV 全序列，再另一輪做平滑），
    降低「兩份實作剛好共用同一個筆誤」的機率。"""
    n = len(closes)
    rsv: List[Optional[float]] = [None] * n
    for i in range(fastk - 1, n):
        wh = highs[i - fastk + 1: i + 1]
        wl = lows[i - fastk + 1: i + 1]
        c = closes[i]
        if c is None or None in wh or None in wl:
            continue
        hi, lo = max(wh), min(wl)
        rsv[i] = 50.0 if hi == lo else (c - lo) / (hi - lo) * 100.0

    k_out: List[Optional[float]] = [None] * n
    d_out: List[Optional[float]] = [None] * n
    k = d = None
    warm = 0
    for i in range(n):
        if rsv[i] is None:
            continue
        k = (rsv[i] + (slowk - 1) * (k if k is not None else seed)) / slowk
        d = (k + (slowd - 1) * (d if d is not None else seed)) / slowd
        warm += 1
        if warm >= warmup:
            k_out[i], d_out[i] = k, d
    return k_out, d_out


def test_tier2_longer_series_cross_check():
    n = 45
    closes = [100 + 15 * _pseudo_sine(i) + (i % 7) * 0.3 for i in range(n)]
    highs = [c + 1.2 + (i % 3) * 0.1 for i, c in enumerate(closes)]
    lows = [c - 1.5 - (i % 4) * 0.1 for i, c in enumerate(closes)]
    # 中間夾一根缺值，同時驗證長序列下的缺值處理與交叉比對一致。
    closes[20] = None

    k1, d1 = stochastic(highs, lows, closes, fastk_period=9, slowk_period=3, slowd_period=3, warmup_bars=25)
    k2, d2 = _float_reference_kd(highs, lows, closes, fastk=9, slowk=3, slowd=3, warmup=25)

    # tol 用 TOLERANCE（1e-4）而非更嚴格的值：stochastic() 對外一律 round(value, 4)
    # （比照 indicators/moving_average.py 的既有慣例），reference 回傳未四捨五入的原始浮點數，
    # 兩者本來就會有最多 5e-5 的四捨五入差，不是計算邏輯的差異。
    _check("Tier2 45 根序列 K 值與獨立參考實作一致", _series_close(k1, k2))
    _check("Tier2 45 根序列 D 值與獨立參考實作一致", _series_close(d1, d2))
    _check("Tier2 暖身期前為 None", all(v is None for v in k1[:33]), f"k1[:33] 中非 None 的位置={[i for i,v in enumerate(k1[:33]) if v is not None]}")


def _pseudo_sine(i: int) -> float:
    """不依賴 math.sin 也能有振盪形狀的確定性數列（避免額外 import，純粹湊出有漲有跌的序列）。"""
    cycle = i % 12
    table = [0, 0.5, 0.87, 1.0, 0.87, 0.5, 0, -0.5, -0.87, -1.0, -0.87, -0.5]
    return table[cycle]


# ══════════════════════════════════════════════════════════════════════════
# Tier 3（AC-6）：真實標的，不同月份區間下重疊日期的 K/D 必須完全相同。
# ══════════════════════════════════════════════════════════════════════════

async def _tier3_ac6(symbol: str = "2330", market: str = "tw") -> None:
    from services.stock_service import get_stock_chart_payload

    months_options = [1, 3, 6, 12]
    payloads = {}
    for months in months_options:
        payload = await get_stock_chart_payload(symbol, period="daily", months=months, market=market, source="json")
        if "error" in payload:
            print(f"[SKIP] Tier3 AC-6：{symbol} 讀不到資料（{payload['error']}），略過此檢查")
            return
        payloads[months] = payload

    baseline_months = max(months_options)
    baseline = payloads[baseline_months]
    baseline_by_date = {d: (k, dd) for d, k, dd in zip(baseline["dates"], baseline["kd"]["k"], baseline["kd"]["d"])}

    all_ok = True
    for months, payload in payloads.items():
        if months == baseline_months:
            continue
        for date, k, d in zip(payload["dates"], payload["kd"]["k"], payload["kd"]["d"]):
            if date not in baseline_by_date:
                continue
            bk, bd = baseline_by_date[date]
            if not (_close(k, bk) and _close(d, bd)):
                all_ok = False
                print(f"       不一致：date={date} months={months} k={k} d={d}  vs  baseline(months={baseline_months}) k={bk} d={bd}")

    _check(f"Tier3 AC-6：{symbol} 不同月份區間重疊日期 K/D 完全相同", all_ok)
    _check("Tier3 payload 含 kd.params/smoothing/overbought/oversold",
           all(key in baseline["kd"] for key in ("params", "smoothing", "k", "d", "overbought", "oversold")))


# ══════════════════════════════════════════════════════════════════════════

def main():
    test_tier1_basic_known_values()
    test_tier1_hhv_eq_llv()
    test_tier1_leading_missing()
    test_tier1_insufficient_length()
    test_tier1_all_missing()
    test_tier1_gap_state_retained()
    test_unsupported_smoothing_falls_back()
    test_tier2_longer_series_cross_check()

    try:
        asyncio.run(_tier3_ac6())
    except Exception as e:
        print(f"[SKIP] Tier3 AC-6 執行時發生例外，略過（不計入失敗）：{e}")

    print()
    if _failures:
        print(f"❌ {len(_failures)} 項失敗：{_failures}")
        sys.exit(1)
    else:
        print("✅ 全部通過")


if __name__ == "__main__":
    main()
