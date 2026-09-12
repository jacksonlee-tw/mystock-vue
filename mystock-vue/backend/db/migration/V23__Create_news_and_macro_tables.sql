-- V23__Create_news_and_macro_tables.sql
-- 輕量化新聞輿情與總經監控（docs/16.AI技術分析/Phase4-輕量化新聞輿情與總經監控.md §7）
-- 三張新表皆為 PostgreSQL 唯一儲存，不參與 DATA_SOURCE 的 JSON/PG 雙軌切換（ADR-P4-07，
-- 比照 ai_analysis_report 的既有決策 ADR-AI-14）。

-- ── stock_news（新聞與情緒，§7.1）──────────────────────────────────────
CREATE TABLE IF NOT EXISTS stock_news (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL REFERENCES symbols(symbol) ON DELETE RESTRICT,
    market_type VARCHAR(10) NOT NULL DEFAULT 'tw',
    source VARCHAR(20) NOT NULL,                 -- 對應 news_sources.yaml 的 id
    title TEXT NOT NULL,                         -- 標題原文
    news_url TEXT NOT NULL,
    published_at TIMESTAMP NOT NULL,             -- 原始發布時間，僅供顯示（§3.4）
    effective_trade_date DATE NOT NULL,           -- Point-in-time 對齊後的交易日，所有計算的時間依據
    title_hash CHAR(64) NOT NULL,                -- 正規化標題 SHA-256，L2 去重用
    simhash BIGINT,                               -- 64-bit SimHash，L3 近似去重用
    is_duplicate BOOLEAN NOT NULL DEFAULT FALSE,  -- L3 判定為重複；情緒計算排除
    duplicate_of_id BIGINT REFERENCES stock_news(id) ON DELETE SET NULL,  -- 指向保留的代表列
    sentiment_score NUMERIC(4, 3),                -- -1.000 ～ 1.000，允許 NULL（尚未評分）
    sentiment_label VARCHAR(10),                  -- BULLISH / BEARISH / NEUTRAL
    sentiment_engine VARCHAR(20),                 -- local(L1) / llm(L2)，供品質稽核
    extra_meta JSONB,                             -- 作者、標籤等擴充欄位
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (symbol, news_url),                                       -- L1 去重
    UNIQUE (symbol, title_hash, effective_trade_date)                -- L2 去重
);

CREATE INDEX IF NOT EXISTS idx_stock_news_query
    ON stock_news (market_type, symbol, effective_trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_stock_news_dedup_scan
    ON stock_news (symbol, published_at DESC);

-- ── stock_discussion_buzz（社群討論度，§7.2）───────────────────────────
CREATE TABLE IF NOT EXISTS stock_discussion_buzz (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL REFERENCES symbols(symbol) ON DELETE RESTRICT,
    market_type VARCHAR(10) NOT NULL DEFAULT 'tw',
    trade_date DATE NOT NULL,
    source VARCHAR(20) NOT NULL,                  -- 例如 'ptt_stock'
    post_count INTEGER NOT NULL DEFAULT 0,
    percentile_rank NUMERIC(5, 4),                 -- 該股自身近 250 交易日分佈的分位數（§4.4）
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source, symbol, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_buzz_symbol_date ON stock_discussion_buzz (symbol, trade_date DESC);

-- ── macro_indicators（總經時序，§7.3）───────────────────────────────────
CREATE TABLE IF NOT EXISTS macro_indicators (
    id BIGSERIAL PRIMARY KEY,
    indicator_code VARCHAR(20) NOT NULL,           -- 'DXY' / 'US10Y' / 'CPI' / 'NFP' / 'FEDFUNDS'
    indicator_date DATE NOT NULL,                  -- 資料所屬期間
    release_date DATE NOT NULL,                    -- 官方公布日（§5.1 look-ahead bias 防線）
    value NUMERIC(18, 6) NOT NULL,
    source VARCHAR(20) NOT NULL DEFAULT 'FRED',
    fetched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (indicator_code, indicator_date)
);

CREATE INDEX IF NOT EXISTS idx_macro_release
    ON macro_indicators (indicator_code, release_date DESC);
