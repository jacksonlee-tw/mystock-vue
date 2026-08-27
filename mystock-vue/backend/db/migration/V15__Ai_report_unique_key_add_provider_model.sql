-- V15__Ai_report_unique_key_add_provider_model.sql
-- 依據《AI 技術分析報告 系統開發規格書》(v3.4) §4.6／ADR-AI-21 修訂唯一鍵：
-- 「同一標的同一交易日只能呼叫一次 LLM」的範圍從 (market_type, symbol, trade_date)
-- 收斂為 (market_type, symbol, trade_date, provider, model)——使用者可在產生報告前
-- 選擇模型；換一個模型視為另一份獨立報告，可以再跑一次；同一個模型同一天仍然只有一份。

-- 1. model 從「事後才知道」的中繼資料，變成「事前就決定」的識別欄位一部分，補上 NOT NULL。
--    先把既有（理論上應該沒有，僅防呆）NULL 值補一個佔位字串，避免 ALTER 失敗。
UPDATE ai_analysis_report SET model = 'unknown' WHERE model IS NULL;
ALTER TABLE ai_analysis_report ALTER COLUMN model SET NOT NULL;

-- 2. 舊唯一索引只鎖 (market_type, symbol, trade_date)，同一天不管換哪個 Provider／模型都擋下來；
--    改成含 provider／model 的新唯一索引。
DROP INDEX IF EXISTS uq_ai_report_daily;
CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_report_daily_model
    ON ai_analysis_report (market_type, symbol, trade_date, provider, model);

-- 3. 依標的查歷史軌跡的索引一併補上 model，讓「這檔各模型分別怎麼看」的查詢也能吃到索引。
DROP INDEX IF EXISTS idx_ai_report_symbol_date;
CREATE INDEX IF NOT EXISTS idx_ai_report_symbol_date
    ON ai_analysis_report (market_type, symbol, trade_date DESC, model);
