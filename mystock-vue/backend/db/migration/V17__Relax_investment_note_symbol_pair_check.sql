-- ============================================================
-- V17__Relax_investment_note_symbol_pair_check.sql
-- 放寬 investment_note 的 market/symbol 配對限制（docs/8.個人投資記帳功能/個人投資筆記.md）
--
-- V16 的 ck_investment_note_symbol_pair 要求 market/symbol 必須同時有值或同時留空，但實務上
-- 使用者常只想標註「這篇筆記跟台股／美股大盤有關」而不指定個股，因此改成：symbol 有值時才強制
-- 要求 market 也有值（不能只給代號、沒給市場），market 則可單獨存在。
-- ============================================================

ALTER TABLE investment_note
    DROP CONSTRAINT IF EXISTS ck_investment_note_symbol_pair;

ALTER TABLE investment_note
    ADD CONSTRAINT ck_investment_note_symbol_pair CHECK (
        symbol IS NULL OR market IS NOT NULL
    );
