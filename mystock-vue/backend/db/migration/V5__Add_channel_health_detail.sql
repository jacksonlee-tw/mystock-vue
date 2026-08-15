-- ============================================================
-- V5__Add_channel_health_detail.sql
-- 補上「連線測試」結果說明的持久化欄位（管道設定頁需常態顯示已連線的帳號，而非僅
-- 測試當下的 Toast 訊息，例如 Telegram 顯示「已連接機器人：@xxx」）
--
-- notify_channel 原本只存 last_health_at（測試時間），沒有存測試結果的說明文字，
-- 因此頁面重新整理後就看不到上次測試回傳的機器人帳號/錯誤原因。新增
-- last_health_detail 對應 channel_config.test_connection() 回傳的 detail 欄位。
-- ============================================================

ALTER TABLE notify_channel
    ADD COLUMN IF NOT EXISTS last_health_detail VARCHAR(200);

COMMENT ON COLUMN notify_channel.last_health_detail IS
    '上次連線測試（health_check）回傳的說明文字，例如 Telegram 的「已連接機器人：@xxx」或失敗原因';
