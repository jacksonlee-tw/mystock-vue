-- ============================================================
-- V18__Add_view_id_to_ai_llm_execution.sql
-- 新增「觸發功能來源」欄位（docs/16.AI技術分析/執行歷史頁面開發計劃.md §2.1）
--
-- ai_llm_execution 原本沒有任何欄位記錄「這次呼叫是被哪個功能觸發的」——現況只有一個功能
-- （個股頁「AI 診股報告」按鈕）會呼叫 LLM，看不出問題；但 Phase5-三層式 AI 決策引擎與戰情室.md
-- 已確認戰情室批次掃描會沿用同一套 ai_analysis.py API 與這張執行紀錄表，屆時同一張表會混著
-- 「使用者手動點擊個股頁」與「排程批次掃描」兩種完全不同性質的呼叫，需要這個欄位才能分辨。
--
-- 比照 activity_log.view_id VARCHAR(60)（V14，「觸發來源畫面」）的既有慣例：不做外鍵、不另建
-- 對照表，沿用自由字串，日後新功能只要在呼叫端傳自己的 view_id 字串即可，不需要再改 schema。
-- 欄位新增前的既有執行紀錄 view_id 為 NULL，代表「早期資料，未記錄」，不可回填猜測。
-- ============================================================

ALTER TABLE ai_llm_execution ADD COLUMN IF NOT EXISTS view_id VARCHAR(60);

-- 依功能來源查詢／統計用（例如「這個月的成本，多少是個股頁點出來的、多少是戰情室掃出來的」）
CREATE INDEX IF NOT EXISTS idx_ai_exec_view_id
    ON ai_llm_execution (view_id, created_at DESC);
