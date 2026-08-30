-- ============================================================
-- V20__Add_granger_columns_to_lead_lag_cache.sql
-- FR-10 格蘭傑因果檢定（docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §4.2、新增 ADR-IC-22）
--
-- ADR-IC-05 原先把 Granger 因果檢定延後至 P2，待 CCF／peak_lag_day 證明有實用價值後再評估；
-- 該延後已由使用者明確解除（見規格書修訂紀錄）。本遷移只新增欄位、不新建資料表——沿用
-- 「一列 = 一條邊、一個計算窗口的領先—落後分析結果」的既有語意（V19 §5.3），CCF 與 Granger
-- 是同一份分析在同一個 window_end 上的兩種統計量，不是兩件事。
--
-- 全部欄位皆為 NULLABLE：
--   1) 既有由 FR-19 CCF 批次寫入的歷史列在本遷移套用當下即為 NULL，語意是「尚未跑過 Granger」，
--      不是「跑過但無顯著性」，兩者不可混淆（比照既有 ai_llm_execution.view_id 新增欄位的既有慣例，
--      見 V18 檔頭註解「欄位新增前的既有執行紀錄視為『早期資料，未記錄』，不可回填猜測」）；
--   2) 樣本不足或 statsmodels 計算失敗的配對（indicators/lead_lag.py 的 granger_causality()
--      回傳 None）本來就不產生 p 值，維持 NULL 是唯一正確的表示方式，不得以 0 或 1 代入。
--
-- granger_p_value_adjusted／granger_significant 是「同一批次」內對所有配對一起做 Benjamini-Hochberg
-- 校正後的結果（見 §13 風險 2「多重比較問題」、indicators/lead_lag.py 的
-- benjamini_hochberg_correction()）——不是對單一配對 p<0.05 的天真判斷。校正批次範圍見
-- industry_chain/lead_lag_job.py 的 compute_granger_for_all_edges() 檔頭說明。
-- ============================================================

ALTER TABLE industry_chain_lead_lag_cache
    ADD COLUMN IF NOT EXISTS granger_p_value          NUMERIC(8, 6),
    ADD COLUMN IF NOT EXISTS granger_p_value_adjusted NUMERIC(8, 6),
    ADD COLUMN IF NOT EXISTS granger_significant      BOOLEAN,
    ADD COLUMN IF NOT EXISTS granger_optimal_lag      SMALLINT;

COMMENT ON COLUMN industry_chain_lead_lag_cache.granger_p_value IS
    'grangercausalitytests()：對 optimal_lag 取 ssr_ftest 的原始（未校正）p-value；NULL 代表尚未跑過
    Granger 或該配對樣本不足／計算失敗（見 indicators/lead_lag.py granger_causality()）';
COMMENT ON COLUMN industry_chain_lead_lag_cache.granger_p_value_adjusted IS
    '同一批次（見 lead_lag_job.py compute_granger_for_all_edges() 檔頭）內對所有配對一起做
    Benjamini-Hochberg 校正（fdr_bh）後的 p-value；不得只看 granger_p_value 判斷顯著性（§13 風險 2）';
COMMENT ON COLUMN industry_chain_lead_lag_cache.granger_significant IS
    '以 granger_p_value_adjusted < IC_GRANGER_ALPHA 判定；一律以此欄位為準，不得由前端或其他
    呼叫端自行拿 granger_p_value 與 0.05 比較（會漏掉多重比較校正，重現 §13 風險 2 描述的假陽性問題）';
COMMENT ON COLUMN industry_chain_lead_lag_cache.granger_optimal_lag IS
    '使 ssr_ftest p-value 最小的延遲天數（1~IC_GRANGER_MAX_LAG）；與 peak_lag_days（CCF 相關係數
    絕對值最大的延遲）是兩個獨立統計量算出的兩個獨立答案，數值不一致是正常現象，不代表其中一個算錯';
