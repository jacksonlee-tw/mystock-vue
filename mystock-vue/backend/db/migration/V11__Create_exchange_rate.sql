-- ============================================================
-- V11__Create_exchange_rate.sql
-- 每日匯率資料（見 docs/8.個人投資記帳功能/個人投資記帳功能_design.md 補充章節）
--
-- 來源：fawazahmed0/currency-api（jsDelivr CDN 為主、pages.dev 為備援，見
-- services/exchange_rate_fetcher.py）。原本規劃抓台灣銀行牌告匯率
-- （rate.bot.com.tw/xrt/flcsv/0/day），但該端點會回傳需要執行 JS 的 bot-challenge 頁面，
-- 從一般伺服器環境的自動化請求無法取得資料，因此改用這個公開、免金鑰、非銀行牌告的市場參考匯率
-- API；只有單一參考匯率（無現金/即期、買入/賣出的區分），所以只存一個 rate 欄位，不比照銀行報價
-- 假裝有買入/賣出兩種價格。
--
-- 目前只收 USD/JPY/CNY；用途：個人投資記帳模組 transactions 頁「折算台幣」欄位依交易日查歷史匯率
-- （見 repositories/exchange_rate_repository.py get_rate_for_date()）。
--
-- 不影響既有的手動 portfolio_settings.fx_rate（dashboard 跨市場 TWD 彙總仍用那個手動值，
-- 這張表的歷史匯率只餵給 transactions 頁的新欄位，兩者刻意分開）。
-- ============================================================
CREATE TABLE IF NOT EXISTS exchange_rate (
    id          BIGSERIAL       PRIMARY KEY,
    rate_date   DATE            NOT NULL,
    currency    VARCHAR(3)      NOT NULL CHECK (currency IN ('USD', 'JPY', 'CNY')),
    rate        NUMERIC(16, 8)  NOT NULL,  -- 1 單位外幣兌換多少 TWD（市場參考匯率，非銀行買入/賣出報價）
    source      VARCHAR(40)     NOT NULL DEFAULT 'fawazahmed0-currency-api',
    fetched_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- 同一天同一幣別只留一筆（重複抓取＝更新，見 upsert_many() 的 ON CONFLICT）
CREATE UNIQUE INDEX IF NOT EXISTS uq_exchange_rate_date_currency
    ON exchange_rate (rate_date, currency);

-- 依幣別找最近一個有資料日期（get_rate_for_date() 的 WHERE currency=? AND rate_date<=? ORDER BY rate_date DESC）
CREATE INDEX IF NOT EXISTS idx_exchange_rate_currency_date
    ON exchange_rate (currency, rate_date DESC);

COMMENT ON COLUMN exchange_rate.rate IS
    '1 單位外幣兌換多少 TWD（單一市場參考匯率，見 exchange_rate_repository.get_rate_for_date()）';
