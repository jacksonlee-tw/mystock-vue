"""領先—落後量化檢定（docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §4.2）。

純函式、不吃 DB、不做 I/O（ADR-IC-04）：比照 indicators/moving_average.py、chip.py 的既有
慣例，本模組只負責「算數值」，只讀已算好的序列，不自己去查資料庫或呼叫爬蟲。輸入一律是
「日報酬率」而非原始價格（先算報酬率以避免趨勢項污染相關係數，AC-IC-3）；把價格轉成報酬率
是呼叫端的責任（daily_returns() 提供這一步的純函式版本，仍需呼叫端自行取得對齊後的價格序列）。

lag 方向定義：`cross_correlation(returns_upstream, returns_downstream, k)` 檢驗「上游第 t 天
的報酬率」與「下游第 t+k 天的報酬率」的相關性——k 越大代表下游反應得越慢。

FR-10（格蘭傑因果檢定，ADR-IC-05 的延後已由使用者明確解除，見規格書修訂紀錄與新增 ADR-IC-22）
新增於本檔尾端：`granger_causality()` 與 CCF 系列函式同一份「單一配對」的檢定邏輯延伸，只是換
一種統計方法回答同一個「上游是否領先下游」的問題；`benjamini_hochberg_correction()` 是批次多重
比較校正的通用純函式，不限定只能配合 Granger 使用。兩者維持與本檔其餘函式相同的純函式約束。
"""
from __future__ import annotations
from typing import Optional

import numpy as np
from scipy.stats import pearsonr
from statsmodels.stats.multitest import multipletests
from statsmodels.tsa.stattools import grangercausalitytests


def align_series(
    dates_a: list, values_a: list[float], dates_b: list, values_b: list[float],
) -> tuple[list, list[float], list[float]]:
    """取兩序列日期交集後回傳 (common_dates, aligned_a, aligned_b)，依交集後的日期由小到大排序。

    刻意不補值：新上市、長期停牌或暫停交易造成的缺口只能靠交集跳過，不得以前值填補或補 0
    ——補值會製造出不存在的同步性（FR-7b、AC-IC-14）。呼叫端如需要序列已經對齊（例如同一份
    ScanContext），仍建議先過一次本函式，確保兩檔標的即使理論上同交易日曆，也不會因個別
    停牌日而錯位比較。"""
    map_a = dict(zip(dates_a, values_a))
    map_b = dict(zip(dates_b, values_b))
    common = sorted(set(map_a.keys()) & set(map_b.keys()))
    return common, [map_a[d] for d in common], [map_b[d] for d in common]


def daily_returns(prices: list[float]) -> list[float]:
    """簡單日報酬率 `p[t] / p[t-1] - 1`。長度比輸入少 1；`0` 一律視為缺值不參與計算
    （比照 CLAUDE.md「fetcher 失敗回填 0.0」的既有已知問題，0 不是合法價格）。"""
    out: list[float] = []
    for i in range(1, len(prices)):
        prev, cur = prices[i - 1], prices[i]
        if not prev or not cur:
            continue
        out.append(cur / prev - 1)
    return out


def cross_correlation(
    returns_upstream: list[float], returns_downstream: list[float], max_lag: int = 30,
) -> list[dict]:
    """回傳 `[{"lag": k, "correlation": r, "sample_size": n}, ...]`，k 由 1 到 `max_lag`。

    每個 lag 各自用「上游序列往前裁掉尾端 k 筆、下游序列往前裁掉頭端 k 筆」對齊後計算
    `scipy.stats.pearsonr`；重疊點數不足 3 筆（pearsonr 的最低要求）時該 lag 直接跳過，
    不硬算一個沒有統計意義的係數。"""
    n = len(returns_upstream)
    if n != len(returns_downstream):
        raise ValueError("returns_upstream 與 returns_downstream 長度必須相同（呼叫前應已用 align_series 對齊）")

    out: list[dict] = []
    for k in range(1, max_lag + 1):
        a = returns_upstream[: n - k]
        b = returns_downstream[k:]
        sample_size = len(a)
        if sample_size < 3:
            continue
        try:
            r, _p = pearsonr(a, b)
        except Exception:
            continue
        out.append({"lag": k, "correlation": round(float(r), 4), "sample_size": sample_size})
    return out


def find_peak_lag(ccf_result: list[dict]) -> Optional[dict]:
    """由 `cross_correlation()` 的結果取 `|correlation|` 最大的一筆，回傳
    `{"peak_lag_day", "correlation", "sample_size"}`；輸入為空（例如全部 lag 都樣本不足）
    時回傳 `None`（FR-7）。"""
    if not ccf_result:
        return None
    best = max(ccf_result, key=lambda row: abs(row["correlation"]))
    return {
        "peak_lag_day": best["lag"],
        "correlation": best["correlation"],
        "sample_size": best["sample_size"],
    }


def sample_confidence(sample_size: int, min_sample: int = 120, low_confidence_sample: int = 250) -> str:
    """FR-7a 的三層樣本數判準：
    - `< min_sample`（預設 120，約半年）：`"unknown"` —— 不得寫入快取表，`peak_lag_day` 視為未知
    - `min_sample` ～ `low_confidence_sample`（預設 250）：`"low"` —— 寫入但標記低信心
    - `>= low_confidence_sample`：`"normal"`

    門檻走參數而非讀 `.env`，保持本模組零 I/O（ADR-IC-04）；呼叫端（未來的排程工作／
    extractor.py）自行從 `industry_chain/config.py` 或 `.env` 取得 `IC_MIN_SAMPLE_SIZE`／
    `IC_LOW_CONFIDENCE_SAMPLE` 後傳入。"""
    if sample_size < min_sample:
        return "unknown"
    if sample_size < low_confidence_sample:
        return "low"
    return "normal"


def granger_causality(
    returns_upstream: list[float], returns_downstream: list[float], max_lag: int = 30,
) -> Optional[dict]:
    """單一配對的 Granger 因果檢定：上游是否『Granger 導致』下游（FR-10）。

    回傳 `{"optimal_lag": int, "p_value": float, "sample_size": int}`；樣本不足或計算失敗回傳
    `None`（比照 `find_peak_lag()` 對空輸入回傳 `None` 的既有慣例，呼叫端不得把 `None` 當成
    「p-value 剛好算不出來所以視為不顯著」，而是「這組配對沒有可信的檢定結果」）。

    呼叫慣例與 `cross_correlation()` 一致：輸入是**日報酬率**（非價格），呼叫前應已用
    `align_series()` 對齊、`daily_returns()` 轉換；`returns_upstream`／`returns_downstream`
    長度必須相同。`statsmodels.tsa.stattools.grangercausalitytests(data, maxlag)` 的欄位順序
    是 `data[:, 0]` 為被解釋變數、`data[:, 1]` 為解釋變數，虛無假設是「第二欄不 Granger 導致
    第一欄」——本函式要問的是「上游導致下游」，因此固定傳入
    `[returns_downstream, returns_upstream]`（下游在前）。

    對每個 `lag ∈ [1, max_lag]` 各自取 `ssr_ftest` 的 p-value（F 檢定：加入上游落後項後，
    對下游的樣本外解釋力是否顯著提升），`optimal_lag` 取 p-value 最小的那一個——這與
    `find_peak_lag()` 從 CCF 陣列中選 `|correlation|` 最大的那一筆是同一種「多個候選延遲天數，
    選最強訊號那個」的類比邏輯，只是判準從「相關係數絕對值最大」換成「因果性統計檢定最顯著」。

    `max_lag` 會依樣本數自動收斂（`grangercausalitytests()` 每個 lag 的 VAR 迴歸需要
    `樣本數 > 4*lag + 5` 左右的觀測值才穩定，比照 `cross_correlation()` 對每個 lag 各自檢查
    `sample_size < 3` 就跳過的保守做法，這裡改成一次算出可承受的最大 lag，避免逐一嘗試到
    statsmodels 內部拋例外）；收斂後可用 lag 數 < 1（樣本太少）直接回傳 `None`，不勉強硬算。

    **不得**在本函式內做 Benjamini-Hochberg 校正——那是跨配對的批次操作，見
    `benjamini_hochberg_correction()`；混在單一配對的純函式裡，呼叫端會誤以為單筆呼叫已經是
    「校正後可信」的結果（§13 風險 2「多重比較問題」）。
    """
    n = len(returns_upstream)
    if n != len(returns_downstream):
        raise ValueError("returns_upstream 與 returns_downstream 長度必須相同（呼叫前應已用 align_series 對齊）")

    # 每個 lag 的 VAR(lag) 迴歸大致有 2*lag 個係數 + 常數項，需要明顯多於此數的觀測值才穩定；
    # 用 4*lag + 5 當保守下限（比 2*lag+1 留出安全邊際），依樣本數反推可承受的最大 lag。
    effective_max_lag = min(max_lag, (n - 5) // 4)
    if effective_max_lag < 1:
        return None

    data = np.column_stack([returns_downstream, returns_upstream])
    try:
        result = grangercausalitytests(data, maxlag=effective_max_lag)
    except Exception:
        return None

    candidates: list[tuple[int, float]] = []
    for lag, (tests, _models) in result.items():
        try:
            p_value = float(tests["ssr_ftest"][1])
        except Exception:
            continue
        if p_value != p_value:  # NaN 檢查（NaN != NaN），statsmodels 在退化樣本下可能回傳 NaN
            continue
        candidates.append((lag, p_value))

    if not candidates:
        return None

    optimal_lag, p_value = min(candidates, key=lambda item: item[1])
    return {"optimal_lag": optimal_lag, "p_value": round(p_value, 6), "sample_size": n}


def benjamini_hochberg_correction(p_values: list[float], alpha: float = 0.05) -> list[tuple[float, bool]]:
    """Benjamini-Hochberg 假發現率（FDR）校正，回傳 `[(adjusted_p, is_significant), ...]`，
    順序與輸入 `p_values` 一一對應（FR-10、§13 風險 2「多重比較問題」的硬性要求）。

    背景：一條產業鏈若有 10 檔上游 × 5 檔下游即產生 50 組配對，同時對 50 組配對各自做
    `p < 0.05` 的天真判斷，即使全部關聯皆為雜訊，預期仍會有約 2～3 組因隨機性而「顯著」
    ——本函式就是為了擋下這個假陽性問題，**必須**在同一批次的所有配對算完 p-value 後、
    一次性呼叫一次，不得每組配對各自呼叫一次（那等同沒有校正，見
    `industry_chain/lead_lag_job.py` 的 `compute_granger_for_all_edges()` 對批次範圍的說明）。

    底層使用 `statsmodels.stats.multitest.multipletests(method="fdr_bh")`：先將 p-value 由小到
    大排序、逐一比較 `p_(i) <= (i/m) * alpha`，取滿足此條件的最大 i 作為顯著性門檻，
    再換算回每筆各自的校正後 p-value；`multipletests()` 內部已處理排序與還原順序，本函式
    只需原樣把它的輸出轉成 `(adjusted_p, is_significant)` 的 tuple 清單。

    空輸入回傳空清單（避免呼叫端還要另外判斷「這批次剛好沒有任何配對」的邊界情況）。
    """
    if not p_values:
        return []
    is_significant, adjusted_p_values, _alpha_sidak, _alpha_bonf = multipletests(
        p_values, alpha=alpha, method="fdr_bh",
    )
    return [(round(float(p), 6), bool(sig)) for p, sig in zip(adjusted_p_values, is_significant)]
