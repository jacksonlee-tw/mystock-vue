-- V9__Create_market_daily_tables.sql
-- 依據《選股功能與爬蟲 整合設計規格書》(v5.1) §3.4、§3.9.4 建立全市場日資料表與作業紀錄表

-- 1. 全市場每日收盤行情
CREATE TABLE IF NOT EXISTS daily_market_quote (
    symbol VARCHAR(20) NOT NULL REFERENCES symbols(symbol) ON DELETE RESTRICT,
    trade_date DATE NOT NULL,
    market_type VARCHAR(10) NOT NULL DEFAULT 'tw',
    exchange VARCHAR(20),
    open_price NUMERIC(15, 4),
    high_price NUMERIC(15, 4),
    low_price NUMERIC(15, 4),
    close_price NUMERIC(15, 4),
    change_amount NUMERIC(15, 4),
    change_percent NUMERIC(10, 4),
    volume BIGINT,
    turnover BIGINT,
    transaction_count INTEGER,
    data_quality VARCHAR(10) NOT NULL DEFAULT 'ok',
    source VARCHAR(20) NOT NULL DEFAULT 'MI_INDEX',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_dmq_date_market ON daily_market_quote (trade_date, market_type);
CREATE INDEX IF NOT EXISTS idx_dmq_date_change ON daily_market_quote (trade_date, change_percent DESC);
CREATE INDEX IF NOT EXISTS idx_dmq_date_turnover ON daily_market_quote (trade_date, turnover DESC);

-- 2. 全市場每日籌碼（三大法人 + 信用交易）
CREATE TABLE IF NOT EXISTS daily_market_chip (
    symbol VARCHAR(20) NOT NULL REFERENCES symbols(symbol) ON DELETE RESTRICT,
    trade_date DATE NOT NULL,
    market_type VARCHAR(10) NOT NULL DEFAULT 'tw',
    exchange VARCHAR(20),
    foreign_net BIGINT,
    trust_net BIGINT,
    dealer_net BIGINT,
    institutional_net BIGINT,
    margin_balance BIGINT,
    margin_buy BIGINT,
    margin_sell BIGINT,
    margin_redeem BIGINT,
    margin_quota BIGINT,
    short_balance BIGINT,
    short_buy BIGINT,
    short_sell BIGINT,
    short_redeem BIGINT,
    offset_amount BIGINT,
    data_quality VARCHAR(10) NOT NULL DEFAULT 'ok',
    source VARCHAR(20) NOT NULL DEFAULT 'T86+MI_MARGN',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_dmc_date_market ON daily_market_chip (trade_date, market_type);
CREATE INDEX IF NOT EXISTS idx_dmc_date_foreign ON daily_market_chip (trade_date, foreign_net DESC);
CREATE INDEX IF NOT EXISTS idx_dmc_date_trust ON daily_market_chip (trade_date, trust_net DESC);

-- 3. 全市場每日估值與市值
CREATE TABLE IF NOT EXISTS daily_valuation (
    symbol VARCHAR(20) NOT NULL REFERENCES symbols(symbol) ON DELETE RESTRICT,
    trade_date DATE NOT NULL,
    market_type VARCHAR(10) NOT NULL DEFAULT 'tw',
    exchange VARCHAR(20),
    pe_ratio NUMERIC(12, 2),
    pb_ratio NUMERIC(12, 2),
    dividend_yield NUMERIC(8, 2),
    market_cap BIGINT,
    mcap_rank INTEGER,
    source VARCHAR(20) NOT NULL DEFAULT 'BWIBBU',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_dv_date_market ON daily_valuation (trade_date, market_type);
CREATE INDEX IF NOT EXISTS idx_dv_date_yield ON daily_valuation (trade_date, dividend_yield DESC);
CREATE INDEX IF NOT EXISTS idx_dv_date_pe ON daily_valuation (trade_date, pe_ratio);
CREATE INDEX IF NOT EXISTS idx_dv_date_mcap_rank ON daily_valuation (trade_date, mcap_rank);

-- 4. 全市場每月營業收入
CREATE TABLE IF NOT EXISTS monthly_revenue (
    symbol VARCHAR(20) NOT NULL REFERENCES symbols(symbol) ON DELETE RESTRICT,
    year_month CHAR(7) NOT NULL,
    market_type VARCHAR(10) NOT NULL DEFAULT 'tw',
    revenue BIGINT,
    mom_percent NUMERIC(10, 2),
    yoy_percent NUMERIC(10, 2),
    announced_date DATE,
    source VARCHAR(20) NOT NULL DEFAULT 'TWSE_OPENAPI',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, year_month)
);

CREATE INDEX IF NOT EXISTS idx_mr_year_month ON monthly_revenue (year_month);
CREATE INDEX IF NOT EXISTS idx_mr_sym_ym ON monthly_revenue (symbol, year_month DESC);

-- 5. 全市場抓取與回補作業紀錄表 (可觀測性與進度追蹤)
CREATE TABLE IF NOT EXISTS market_fetch_job (
    id BIGSERIAL PRIMARY KEY,
    scope VARCHAR(20) NOT NULL DEFAULT 'daily',
    targets VARCHAR(100) NOT NULL DEFAULT 'quote,chip,valuation',
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    cursor_date DATE,
    total_days INTEGER NOT NULL DEFAULT 0,
    done_days INTEGER NOT NULL DEFAULT 0,
    failed_days INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    last_error TEXT,
    trigger_type VARCHAR(20) NOT NULL DEFAULT 'schedule',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mfj_status_created ON market_fetch_job (status, created_at DESC);
