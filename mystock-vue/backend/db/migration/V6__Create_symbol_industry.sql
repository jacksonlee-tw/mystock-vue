-- ============================================================
-- V6__Create_symbol_industry.sql
-- 個股產業標籤（大盤指數功能規劃書 §8.2）：讓熱力圖／投組配置圓餅圖能依產業分組，
-- 與「類股指數」（大盤指數功能規劃書 ADR-I1，存在 symbols/daily_stock_data）是兩個不同的
-- 概念——這裡存的是「某檔個股屬於哪個產業」的靜態標籤，非每日變動的行情資料，
-- 所以獨立成一張表，不塞進 daily_stock_data 或 symbols。
--
-- industry_code 台股沿用 TWSE 官方產業分類代碼（見 backend/markets/tw_industries.py 的
-- TWSE_INDUSTRY_MAP，"01"~"91"）；美股沿用 yfinance 的 sector（GICS 近似），
-- 兩個市場的代碼命名空間不同，因此不建跨市場的 FOREIGN KEY 到單一產業字典表，
-- 只在應用層（services/industry_fetcher.py）各自對應顯示名稱。
-- ============================================================

CREATE TABLE IF NOT EXISTS symbol_industry (
    symbol         VARCHAR(20) NOT NULL REFERENCES symbols(symbol) ON DELETE CASCADE,
    market_type    VARCHAR(10) NOT NULL,
    industry_code  VARCHAR(20) NOT NULL,
    industry_name  VARCHAR(100) NOT NULL,
    updated_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (symbol)
);

CREATE INDEX IF NOT EXISTS idx_symbol_industry_market_code
    ON symbol_industry (market_type, industry_code);

COMMENT ON TABLE symbol_industry IS '個股產業標籤（靜態中繼資料，非每日行情），見大盤指數功能規劃書 §8.2';
COMMENT ON COLUMN symbol_industry.industry_code IS
    '台股＝TWSE 官方產業分類代碼（見 markets/tw_industries.py）；美股＝yfinance sector 代碼';
