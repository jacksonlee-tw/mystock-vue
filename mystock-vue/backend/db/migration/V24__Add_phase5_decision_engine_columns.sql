-- V24__Add_phase5_decision_engine_columns.sql
-- Phase 5：三層式 AI 決策引擎與戰情室（docs/16.AI技術分析/Phase5-三層式 AI 決策引擎與戰情室.md §5）
-- 對既有 ai_analysis_report 做加法欄位擴充，不觸碰 V14/V15 已套用的既有欄位（CLAUDE.md 規定）。

-- FR-5.2：目標價，語意與既有 stop_loss 對稱（下檔防守 vs 上檔滿足點）
ALTER TABLE ai_analysis_report ADD COLUMN target_price NUMERIC(15, 4);

-- FR-5.3：手動 vs 批次來源，供 §8 配額拆分（AI_DAILY_QUOTA vs AI_BATCH_DAILY_QUOTA）各自計算
ALTER TABLE ai_analysis_report ADD COLUMN trigger_type VARCHAR(10) NOT NULL DEFAULT 'manual';

-- FR-5.6：AI 研判與規則引擎當日訊號的比對結果，'aligned' | 'diverged' | NULL（無可比對訊號或中性評等）
ALTER TABLE ai_analysis_report ADD COLUMN rule_signal_alignment VARCHAR(10);

CREATE INDEX idx_ai_report_trigger_type ON ai_analysis_report (trigger_type, generated_at);
