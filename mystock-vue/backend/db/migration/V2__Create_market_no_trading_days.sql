-- 對應 phase3_5 設計文件第 3.5 節：把「這天沒開盤」的資訊從 JSON 快取檔改為資料庫管理，
-- 讓「缺漏」與「當天沒開盤」可以被區分，避免回補作業每次啟動都重抓假日。

CREATE TABLE market_no_trading_days (
    market_type VARCHAR(10) NOT NULL,
    trade_date  DATE        NOT NULL,
    source      VARCHAR(20) NOT NULL DEFAULT 'probed',  -- probed | manual | calendar
    created_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
    PRIMARY KEY (market_type, trade_date)
);
