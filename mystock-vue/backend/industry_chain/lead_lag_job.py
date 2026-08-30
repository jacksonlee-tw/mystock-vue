"""
industry_chain/lead_lag_job.py
FR-19：全量重算所有 active 邊的 CCF，寫入 industry_chain_lead_lag_cache（見
docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §4.2、§4.6）。

只做「重算」這一件事——BFS／候選篩選（graph.py／spillover.py）不在本檔，那些留待後續批次。
取價序列的路徑比照 services/chip_provider.py 已驗證過的既有作法：
`load_stock_data()` → `aggregate_stock_data()`，不重新發明第二套資料存取邏輯。

FR-10（格蘭傑因果檢定，ADR-IC-05 延後已解除，見規格書修訂紀錄與新增 ADR-IC-22）新增於本檔尾端：
`compute_granger_for_all_edges()`。刻意做成獨立函式而非塞進 `recompute_all_lead_lag()` 內部，
理由：(1) Benjamini-Hochberg 多重比較校正（§13 風險 2）需要「同一批次的全部 p-value 先收集完
才能一次校正」，跟 CCF 逐邊算完就逐邊寫入的迴圈結構不同，硬塞在一起會讓兩種迴圈邏輯互相糾纏；
(2) 保留 `recompute_all_lead_lag()` 單獨呼叫的能力（例如只想重算 CCF、不跑較昂貴的 Granger 檢定）。
兩者的呼叫順序由 `services/scheduler.py` 的 `_scheduled_industry_chain_ccf()` 負責串接
（CCF 先、Granger 後——Granger 只處理「CCF 已確認樣本數足夠」的邊，見 FR-19、FR-10 的既有定義）。

Granger 相關的環境變數設定**不**經由 `industry_chain/config.py`（該模組正被另一條開發支線
同步擴充 §4.7 grounded 萃取設定，直接改動會增加不必要的合併衝突面）：本檔案自備
`_env_int()`／`_env_float()` 兩個區域小工具，比照 `industry_chain/config.py`／`ai/config.py`
既有的「每次呼叫重新讀 .env、免重啟」慣例，僅供本檔案內部使用。
"""
from __future__ import annotations
import logging
import os
from datetime import date, datetime, timedelta

from dotenv import load_dotenv

from config import ENV_PATH, MAX_HISTORY_MONTHS
from db.session import get_async_session
from indicators.lead_lag import (
    align_series, benjamini_hochberg_correction, cross_correlation, daily_returns,
    find_peak_lag, granger_causality, sample_confidence,
)
from repositories.industry_chain_repository import IndustryChainRepository
from services.stock_service import aggregate_stock_data, load_stock_data

logger = logging.getLogger("mystock-backend")

MIN_SAMPLE_SIZE = 120
LOW_CONFIDENCE_SAMPLE = 250
MAX_LAG_DAYS = 30


# ── FR-10 環境變數讀取（區域小工具，見檔頭說明：刻意不放進 industry_chain/config.py）──
def _env_int(key: str, default: int) -> int:
    load_dotenv(ENV_PATH, override=True)
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    load_dotenv(ENV_PATH, override=True)
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


async def price_series(symbol: str, market: str) -> tuple[list[str], list[float]]:
    """回傳 (dates, closes)，剔除 0／缺值（CLAUDE.md 既有共識：0 視為缺值，不得參與計算）。"""
    raw = await load_stock_data(symbol, market)
    if not raw:
        return [], []
    records = aggregate_stock_data(raw, period="daily", months=MAX_HISTORY_MONTHS)
    dates, closes = [], []
    for rec in records:
        close = rec.get("close")
        if not close:
            continue
        dates.append(rec["date"])
        closes.append(float(close))
    return dates, closes


async def _compute_edge_lead_lag(edge: dict) -> dict | None:
    """回傳供 upsert_lead_lag_cache() 用的 kwargs 字典；樣本不足（FR-7a）時回傳 None，
    呼叫端不得寫入快取。"""
    up_dates, up_closes = await price_series(edge["upstream_symbol"], edge["upstream_market"])
    down_dates, down_closes = await price_series(edge["downstream_symbol"], edge["downstream_market"])
    if len(up_closes) < 2 or len(down_closes) < 2:
        return None

    common_dates, aligned_up, aligned_down = align_series(up_dates, up_closes, down_dates, down_closes)
    if len(common_dates) < 2:
        return None

    up_returns = daily_returns(aligned_up)
    down_returns = daily_returns(aligned_down)
    # daily_returns() 長度比輸入少 1，兩者已對齊日期故長度一致
    ccf = cross_correlation(up_returns, down_returns, max_lag=MAX_LAG_DAYS)
    peak = find_peak_lag(ccf)

    sample_size = peak["sample_size"] if peak else len(up_returns)
    confidence = sample_confidence(sample_size, MIN_SAMPLE_SIZE, LOW_CONFIDENCE_SAMPLE)
    if confidence == "unknown":
        return None  # FR-7a：< IC_MIN_SAMPLE_SIZE 不得寫入快取表

    window_end = date.fromisoformat(common_dates[-1]) if common_dates else datetime.now().date()
    window_start = date.fromisoformat(common_dates[0]) if common_dates else window_end - timedelta(days=1)

    return {
        "edge_id": edge["id"],
        "window_start": window_start,
        "window_end": window_end,
        "peak_lag_days": peak["peak_lag_day"] if peak else None,
        "correlation_coefficient": peak["correlation"] if peak else None,
        "sample_size": sample_size,
    }


async def recompute_all_lead_lag(chain_id: str | None = None) -> dict:
    """FR-19 排程主體：全量重算而非增量（§13 已估算此規模下全量重算完全可行）。單一邊計算
    失敗不影響其餘邊（比照既有爬蟲「單檔失敗不中斷整體」的容錯慣例）。"""
    async with get_async_session() as session:
        repo = IndustryChainRepository(session)
        edges = await repo.list_edges(chain_id=chain_id, is_active=True)

        processed = written = skipped_unknown = failed = 0
        for edge in edges:
            processed += 1
            try:
                cache_kwargs = await _compute_edge_lead_lag(edge)
            except Exception as e:
                failed += 1
                logger.warning(f"[產業鏈] 邊 {edge['upstream_symbol']}->{edge['downstream_symbol']} CCF 計算失敗: {e}")
                continue
            if cache_kwargs is None:
                skipped_unknown += 1
                continue
            await repo.upsert_lead_lag_cache(**cache_kwargs)
            written += 1

        await session.commit()

    result = {"processed": processed, "written": written, "skipped_unknown": skipped_unknown, "failed": failed}
    logger.info(f"[產業鏈] CCF 全量重算完成: {result}")
    return result


# ── FR-10：格蘭傑因果檢定（見檔頭說明；排在 recompute_all_lead_lag() 之後執行）─────

async def _compute_edge_granger(edge: dict, min_sample_size: int, max_lag: int) -> dict | None:
    """單一邊的 Granger 前置計算：取價、對齊、轉報酬率、呼叫純函式。回傳供
    `compute_granger_for_all_edges()` 收集 p-value 用的 `{"edge_id", "window_end", "p_value",
    "optimal_lag"}`；樣本不足（未達 `min_sample_size`，見 `IC_GRANGER_MIN_SAMPLE_SIZE`）或
    `granger_causality()` 本身回傳 `None`（樣本仍不足以支撐 `max_lag`、或 statsmodels 計算失敗）
    時回傳 `None`，呼叫端不得計入這批次的 p-value（未檢定的配對不能參與 BH 校正）。

    刻意重新走一次 `price_series()`／`align_series()`／`daily_returns()`，不直接讀
    `industry_chain_lead_lag_cache` 裡 CCF 剛算好的中間值——CCF／Granger 是兩個獨立統計方法，
    各自的取樣與樣本數門檻本就可能不同（Granger 對每個 lag 的 VAR 迴歸比 CCF 的單純相關係數
    更吃樣本，見 `IC_GRANGER_MIN_SAMPLE_SIZE` 預設值高於 CCF 的 `IC_MIN_SAMPLE_SIZE` 的說明），
    共用中間值反而會讓兩者的樣本口徑在未來各自調整參數時悄悄綁死在一起。"""
    up_dates, up_closes = await price_series(edge["upstream_symbol"], edge["upstream_market"])
    down_dates, down_closes = await price_series(edge["downstream_symbol"], edge["downstream_market"])
    if len(up_closes) < 2 or len(down_closes) < 2:
        return None

    common_dates, aligned_up, aligned_down = align_series(up_dates, up_closes, down_dates, down_closes)
    if len(common_dates) < 2:
        return None

    up_returns = daily_returns(aligned_up)
    down_returns = daily_returns(aligned_down)
    sample_size = len(up_returns)
    if sample_size < min_sample_size:
        return None  # 對應 FR-7a 的同一種精神：樣本不足就不檢定，不硬算一個不可信的 p-value

    result = granger_causality(up_returns, down_returns, max_lag=max_lag)
    if result is None:
        return None

    window_end = date.fromisoformat(common_dates[-1])
    return {
        "edge_id": edge["id"],
        "window_end": window_end,
        "p_value": result["p_value"],
        "optimal_lag": result["optimal_lag"],
    }


async def compute_granger_for_all_edges(chain_id: str | None = None) -> dict:
    """FR-10 批次主體：對所有 active 邊計算 Granger 因果檢定，**同一批次的全部 p-value 收集齊
    全後才一次呼叫 `benjamini_hochberg_correction()`**（§13 風險 2「多重比較問題」的硬性要求，
    絕不允許每組配對各自用未校正的 p-value 判斷顯著性）。

    **多重比較校正範圍的設計判斷（globally across chains per run，而非 per chain per run）**：
    本函式對 `chain_id=None`（預設，供排程呼叫）時，是把**這次執行涵蓋的所有產業鏈、所有邊**
    一起收集 p-value 後校正一次，而不是每條鏈各自校正一次。理由：
    (1) §13 風險 2 的算式（10 上游 × 5 下游 = 50 組配對，預期 2～3 組假陽性）描述的是「同時執行
        的檢定總數」造成的假陽性膨脹，跟這些配對來自同一條鏈還是不同鏈無關——分鏈各自校正會
        讓每次校正的 `m`（檢定數）變小，FDR 校正的門檻反而變寬鬆，**削弱**校正的保護力度，
        與「必須做多重比較校正」的原始目的背道而馳；
    (2) 一次批次執行本來就是「這次總共測了幾組配對」的自然單位（比照 FR-19 CCF 全量重算的
        「全量」定義同樣是整批一起算，不分鏈），沒有理由校正邊界要比執行邊界更細；
    (3) 若呼叫端明確傳入 `chain_id`（例如未來 API 想「只重算某一條鏈」的手動觸發端點），
        校正範圍自然縮小為該次呼叫實際涵蓋的邊集合——這是呼叫端主動限縮批次範圍的結果，
        不是本函式對同一批次內部再切分小批次分別校正。
    換句話說：**校正範圍＝本次函式呼叫實際測試的配對集合**，而不是「全站歷史累積的所有配對」
    （不同批次、不同 `window_end` 的檢定結果不會互相污染彼此的校正），也不是「每條鏈各自一批」。

    只對 Granger 前置樣本數（`IC_GRANGER_MIN_SAMPLE_SIZE`，見 `_compute_edge_granger()`）足夠的
    邊計算；寫回前必須已有 FR-19 算出的 CCF 快取列（`update_granger_result()` 是 UPDATE 不是
    upsert，找不到對應列時回傳 0，見該方法 docstring），因此本函式應排在 `recompute_all_lead_lag()`
    之後執行（`services/scheduler.py` 的 `_scheduled_industry_chain_ccf()` 負責此順序）。

    單一邊計算失敗不影響其餘邊（比照 `recompute_all_lead_lag()`／既有爬蟲的既有容錯慣例）。
    成功與失敗皆寫 `activity_log`（`IC_GRANGER_COMPLETE`，比照《AI 報告規格》ADR-AI-18／
    §4.6「執行結果寫 activity_log」的既有規範；寫 log 失敗不得讓主流程失敗）。
    """
    max_lag = _env_int("IC_GRANGER_MAX_LAG", 30)
    alpha = _env_float("IC_GRANGER_ALPHA", 0.05)
    min_sample_size = _env_int("IC_GRANGER_MIN_SAMPLE_SIZE", 150)

    async with get_async_session() as session:
        repo = IndustryChainRepository(session)
        edges = await repo.list_edges(chain_id=chain_id, is_active=True)

        processed = 0
        failed = 0
        skipped_insufficient = 0
        pending: list[dict] = []  # 通過樣本門檻、已算出原始 p-value，尚待批次校正與寫回
        for edge in edges:
            processed += 1
            try:
                outcome = await _compute_edge_granger(edge, min_sample_size, max_lag)
            except Exception as e:
                failed += 1
                logger.warning(
                    f"[產業鏈] 邊 {edge['upstream_symbol']}->{edge['downstream_symbol']} Granger 計算失敗: {e}"
                )
                continue
            if outcome is None:
                skipped_insufficient += 1
                continue
            pending.append(outcome)

        # 多重比較校正：見上方 docstring「校正範圍」說明，範圍固定為本次呼叫收集到的 pending 全體
        corrections = benjamini_hochberg_correction([item["p_value"] for item in pending], alpha=alpha)

        written = 0
        significant = 0
        not_found = 0
        for item, (adjusted_p, is_significant) in zip(pending, corrections):
            rowcount = await repo.update_granger_result(
                edge_id=item["edge_id"],
                window_end=item["window_end"],
                granger_p_value=item["p_value"],
                granger_p_value_adjusted=adjusted_p,
                granger_significant=is_significant,
                granger_optimal_lag=item["optimal_lag"],
            )
            if rowcount:
                written += 1
                if is_significant:
                    significant += 1
            else:
                not_found += 1
                logger.warning(
                    f"[產業鏈] 邊 id={item['edge_id']} window_end={item['window_end']} 找不到對應的 "
                    f"CCF 快取列可更新 Granger 結果（FR-19 尚未針對此 window_end 寫入，已跳過）"
                )

        summary = {
            "processed": processed,
            "tested": len(pending),
            "written": written,
            "significant": significant,
            "skipped_insufficient": skipped_insufficient,
            "not_found": not_found,
            "failed": failed,
            "alpha": alpha,
        }

        try:
            from repositories.activity_log_repository import ActivityLogRepository
            await ActivityLogRepository(session).log(
                code="IC_GRANGER_COMPLETE",
                success=(failed == 0),
                comments=(
                    f"processed={processed} tested={len(pending)} written={written} "
                    f"significant={significant} skipped_insufficient={skipped_insufficient} "
                    f"not_found={not_found} failed={failed} alpha={alpha}"
                ),
            )
        except Exception as e:
            logger.warning(f"[產業鏈] Granger activity_log 寫入失敗（不影響主流程）: {e}")

        await session.commit()

    logger.info(f"[產業鏈] Granger 因果檢定批次完成: {summary}")
    return summary
