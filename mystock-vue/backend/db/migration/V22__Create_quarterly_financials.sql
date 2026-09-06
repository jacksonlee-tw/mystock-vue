-- V22__Create_quarterly_financials.sql
-- 季報 EPS 與損益摘要落庫（docs/16.AI技術分析/Phase2-籌碼面與基本面量化擴充.md §10.4 E-1）
-- 資料來源：TWSE OpenAPI t187ap14_L（各產業 EPS 統計）＋ t187ap06_L_*（綜合損益表各業別），
-- 逐檔補洞則由 services/mops_eps_fetcher.py 以 source='MOPS' 寫入。

CREATE TABLE IF NOT EXISTS quarterly_financials (
    symbol VARCHAR(20) NOT NULL REFERENCES symbols(symbol) ON DELETE RESTRICT,
    year_quarter CHAR(7) NOT NULL,              -- 'YYYY-Qn'（西元年）
    market_type VARCHAR(10) NOT NULL DEFAULT 'tw',
    eps NUMERIC(10, 2),
    revenue BIGINT,
    operating_income BIGINT,
    net_income BIGINT,
    announced_date DATE,
    source VARCHAR(20) NOT NULL DEFAULT 'TWSE_OPENAPI',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, year_quarter)
);

CREATE INDEX IF NOT EXISTS idx_qf_year_quarter ON quarterly_financials (year_quarter);
CREATE INDEX IF NOT EXISTS idx_qf_sym_yq ON quarterly_financials (symbol, year_quarter DESC);
CREATE INDEX IF NOT EXISTS idx_qf_yq_eps ON quarterly_financials (year_quarter, eps DESC);
