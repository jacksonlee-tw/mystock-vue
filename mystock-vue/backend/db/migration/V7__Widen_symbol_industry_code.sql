-- ============================================================
-- V7__Widen_symbol_industry_code.sql
-- 加寬 symbol_industry.industry_code 欄位（大盤指數功能規劃書 §8.2）。
--
-- 背景：V6 建表時把 industry_code 訂為 VARCHAR(20)，設計時只想著台股的官方短代碼
-- （"01"~"91"，見 markets/tw_industries.py）。實測美股 industry_fetcher.py 用 yfinance
-- sector 字串當代碼時，"Communication Services" 等原始字串會撐爆 20 字元，導致整批
-- upsert 在同一個 INSERT 陳述式中被回滾（多筆 VALUES 只要一筆超長，全部一起失敗）。
-- 應用層已改用穩定短代碼（US_SECTOR_CODE_MAP，如 "communication"）修正這個問題，
-- 這裡額外加寬到 50 字元純粹是防禦性余裕，避免未來任何一邊的代碼命名方式再次撐爆欄位。
-- ============================================================

ALTER TABLE symbol_industry
    ALTER COLUMN industry_code TYPE VARCHAR(50);
