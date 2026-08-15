-- ============================================================
-- V8__Create_portfolio_ledger.sql
-- 個人投資記帳與績效追蹤模組（docs/8.個人投資記帳功能/個人投資記帳功能_design.md）
--
-- 這個子系統不走 backend/data/{tw,us}/*.json 那套「爬蟲行情 JSON/Postgres 雙軌」；
-- 這裡存的是使用者手動輸入的交易性資料（買賣、股利、出入金、觀察名單），天生關聯式
-- （FIFO 配對、刪除要重新驗證庫存不能為負），直接建 Postgres 表，比照整合訊息通知平台
-- （V3__Create_notification_platform.sql）新子系統直接上 Postgres、不走 JSON 的先例。
--
-- fee/tax 一律在寫入當下算好凍結（見 services/portfolio_ledger.py），不是「未覆寫就即時
-- 依目前設定重算」——使用者事後調整費率設定，不能讓歷史交易的已實現損益跟著變動。
-- ============================================================

-- ── 交易紀錄 ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS portfolio_transaction (
    id              BIGSERIAL       PRIMARY KEY,
    market          VARCHAR(10)     NOT NULL CHECK (market IN ('tw', 'us')),
    symbol          VARCHAR(20)     NOT NULL,
    name            VARCHAR(100)    NOT NULL,
    side            VARCHAR(10)     NOT NULL CHECK (side IN ('buy', 'sell')),
    trade_date      DATE            NOT NULL,
    trade_time      TIME,
    shares          NUMERIC(18, 4)  NOT NULL CHECK (shares > 0),
    price           NUMERIC(18, 4)  NOT NULL CHECK (price > 0),
    odd_lot         BOOLEAN         NOT NULL DEFAULT FALSE,
    fee             NUMERIC(18, 4)  NOT NULL DEFAULT 0,
    tax             NUMERIC(18, 4)  NOT NULL DEFAULT 0,
    fee_is_manual   BOOLEAN         NOT NULL DEFAULT FALSE,
    tax_is_manual   BOOLEAN         NOT NULL DEFAULT FALSE,
    note            TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_portfolio_transaction_symbol
    ON portfolio_transaction (market, symbol, trade_date);
CREATE INDEX IF NOT EXISTS idx_portfolio_transaction_date
    ON portfolio_transaction (trade_date);

COMMENT ON COLUMN portfolio_transaction.fee IS
    '寫入當下算好並凍結（未手動覆寫時依 portfolio_settings 當時的費率試算），事後調整設定不會回頭改動已存的值';
COMMENT ON COLUMN portfolio_transaction.tax IS '台股＝證交稅（一般 0.3%／ETF 0.1%）；美股＝賣出 SEC 規費，買進恆為 0';

-- ── 股利紀錄 ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS portfolio_dividend (
    id          BIGSERIAL       PRIMARY KEY,
    market      VARCHAR(10)     NOT NULL CHECK (market IN ('tw', 'us')),
    symbol      VARCHAR(20)     NOT NULL,
    name        VARCHAR(100)    NOT NULL,
    pay_date    DATE            NOT NULL,
    type        VARCHAR(10)     NOT NULL CHECK (type IN ('cash', 'stock')),
    amount      NUMERIC(18, 4)  CHECK (amount IS NULL OR amount >= 0),
    shares      NUMERIC(18, 4)  CHECK (shares IS NULL OR shares >= 0),
    note        TEXT,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_portfolio_dividend_amount_shape CHECK (
        (type = 'cash'  AND amount IS NOT NULL) OR
        (type = 'stock' AND shares IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_portfolio_dividend_symbol
    ON portfolio_dividend (market, symbol, pay_date);

-- ── 資金出入金 ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS portfolio_cashflow (
    id          BIGSERIAL       PRIMARY KEY,
    flow_date   DATE            NOT NULL,
    type        VARCHAR(10)     NOT NULL CHECK (type IN ('deposit', 'withdraw')),
    amount      NUMERIC(18, 4)  NOT NULL CHECK (amount > 0),
    note        TEXT,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_portfolio_cashflow_date ON portfolio_cashflow (flow_date);

-- ── 觀察名單（設計文件 §五）──────────────────────────────────
CREATE TABLE IF NOT EXISTS portfolio_watchlist (
    id           BIGSERIAL       PRIMARY KEY,
    market       VARCHAR(10)     NOT NULL CHECK (market IN ('tw', 'us')),
    symbol       VARCHAR(20)     NOT NULL,
    name         VARCHAR(100)    NOT NULL,
    added_date   DATE            NOT NULL DEFAULT CURRENT_DATE,
    target_price NUMERIC(18, 4)  NOT NULL CHECK (target_price > 0),
    note         TEXT,
    created_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- 同一代碼在同一市場僅能存在一筆觀察紀錄（設計文件 §五：重複加入視為更新，不新增重複資料）
CREATE UNIQUE INDEX IF NOT EXISTS uq_portfolio_watchlist_market_symbol
    ON portfolio_watchlist (market, symbol);

-- ── 記帳參數設定（單一列，比照原型「設定」頁）───────────────
CREATE TABLE IF NOT EXISTS portfolio_settings (
    id                  SMALLINT        PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    tw_fee_rate         NUMERIC(10, 6)  NOT NULL DEFAULT 0.001425,
    tw_fee_discount     NUMERIC(4, 3)   NOT NULL DEFAULT 0.6,
    tw_fee_min          NUMERIC(10, 2)  NOT NULL DEFAULT 20,
    tw_tax_rate         NUMERIC(10, 6)  NOT NULL DEFAULT 0.003,
    tw_tax_rate_etf     NUMERIC(10, 6)  NOT NULL DEFAULT 0.001,
    us_fee_rate         NUMERIC(10, 6)  NOT NULL DEFAULT 0,
    us_sec_fee_rate     NUMERIC(12, 8)  NOT NULL DEFAULT 0.0000278,
    fx_rate             NUMERIC(10, 4)  NOT NULL DEFAULT 32.5,
    cost_method         VARCHAR(10)     NOT NULL DEFAULT 'fifo' CHECK (cost_method IN ('fifo', 'average')),
    dividend_mode       VARCHAR(20)     NOT NULL DEFAULT 'income' CHECK (dividend_mode IN ('income', 'reduce_cost')),
    near_target_pct     NUMERIC(5, 2)   NOT NULL DEFAULT 3,
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

INSERT INTO portfolio_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE portfolio_settings IS
    '記帳試算參數（手續費/稅率/匯率/成本法/股利處理法），透過 GET/PUT /api/v1/settings 由前端設定頁調整；'
    '單一列，非部署層 .env 設定';
