-- 對應設計文件第 3.1 節：symbols / daily_stock_data / crawler_logs 三張表與索引

CREATE TABLE symbols (
    symbol        VARCHAR(20) PRIMARY KEY,
    market_type   VARCHAR(10) NOT NULL,
    name          VARCHAR(100),
    exchange      VARCHAR(20),
    security_type VARCHAR(20),
    status        VARCHAR(20) NOT NULL DEFAULT 'active',
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE daily_stock_data (
    id                   BIGSERIAL PRIMARY KEY,
    symbol               VARCHAR(20) NOT NULL REFERENCES symbols(symbol),
    market_type          VARCHAR(10) NOT NULL,
    trade_date           DATE NOT NULL,
    open_price           NUMERIC(15, 4),
    high_price           NUMERIC(15, 4),
    low_price            NUMERIC(15, 4),
    close_price          NUMERIC(15, 4),
    volume               BIGINT,
    turnover             BIGINT,
    transaction_count    INTEGER,
    market_specific_data JSONB,
    created_at           TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Upsert 基準，防重複寫入同一天資料
CREATE UNIQUE INDEX uq_daily_stock_data_symbol_trade_date ON daily_stock_data (symbol, trade_date);
-- 範圍查詢／市場分區
CREATE INDEX idx_daily_stock_data_trade_date_market ON daily_stock_data (trade_date, market_type);
-- JSON 存在性／包含查詢（?、@> 運算子）
CREATE INDEX idx_daily_stock_data_market_specific_data ON daily_stock_data USING GIN (market_specific_data);
-- 高頻數值範圍查詢範例（外資買賣超），GIN 涵蓋不到數值比較，見設計文件第 3.1 節
CREATE INDEX idx_daily_foreign_net_buy ON daily_stock_data (
    ((market_specific_data->'institutional_investors'->>'foreign_net_buy')::numeric)
);

CREATE TABLE crawler_logs (
    id               BIGSERIAL PRIMARY KEY,
    market_type      VARCHAR(10) NOT NULL,
    trigger_type     VARCHAR(20) NOT NULL,
    started_at       TIMESTAMP NOT NULL,
    finished_at      TIMESTAMP,
    status           VARCHAR(20) NOT NULL,
    symbols_success  INTEGER NOT NULL DEFAULT 0,
    symbols_failed   INTEGER NOT NULL DEFAULT 0,
    error_message    TEXT
);

-- 查詢某市場最近一次執行
CREATE INDEX idx_crawler_logs_market_started ON crawler_logs (market_type, started_at);
