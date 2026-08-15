-- ============================================================
-- V4__Add_recipient_preference_ceiling.sql
-- 補上「系統擁有者指派範圍」與「收件人目前選擇」的欄位區隔（FR-SS-08、AC-24）
--
-- notify_recipient_preference 原本只有一組 allowed_* 欄位，語意上是「收件人目前的
-- 有效偏好」（見需求規格書 §9.1：「收件人可在管理者授權範圍內自行收窄的訂閱條件」）。
-- 但「授權範圍」（ceiling）與「目前選擇」（selected）若共用同一組欄位，就無法區分
-- 「這是誰改的、能否再收窄」，FR-SS-08「只能收窄，不能放寬」也就無從驗證。
-- 因此新增一組 ceiling_* 欄位代表擁有者指派的上限，預設等於全範圍（沿用既有預設值）；
-- 既有 allowed_* 欄位重新定義為「收件人目前的有效選擇」，語意不變、資料不需搬遷。
-- ============================================================

ALTER TABLE notify_recipient_preference
    ADD COLUMN IF NOT EXISTS ceiling_markets             JSONB NOT NULL DEFAULT '["tw","us"]',
    ADD COLUMN IF NOT EXISTS ceiling_strengths           JSONB NOT NULL DEFAULT '["strong","moderate","weak"]',
    ADD COLUMN IF NOT EXISTS ceiling_signal_types        JSONB NOT NULL DEFAULT '["BUY","SELL","WARNING"]',
    ADD COLUMN IF NOT EXISTS ceiling_strategy_categories JSONB NOT NULL DEFAULT '["technical","chip","fundamental"]';

COMMENT ON COLUMN notify_recipient_preference.allowed_markets IS
    '收件人目前的有效選擇（自助頁可調整，須為 ceiling_markets 的子集）';
COMMENT ON COLUMN notify_recipient_preference.ceiling_markets IS
    '系統擁有者指派的授權上限（只能由管理介面調整，自助頁唯讀顯示）';
