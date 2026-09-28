-- V25__Create_forum_sentiment_tables.sql
-- PTT 論壇情緒分析（docs/16.AI技術分析/Phase7-PTT論壇情緒分析.md §4）
-- 兩張新表直接以 PostgreSQL 為唯一儲存，不參與 DATA_SOURCE 的 JSON/PG 雙軌切換（比照
-- Phase 4 ADR-P4-07 的既有決策：雙軌是為 OHLCV 設計，論壇資料不值得再做一套）。
--
-- 與既有 stock_news / stock_discussion_buzz 完全隔離（ADR-P7-03）：獨立資料表，不共用任何
-- 欄位或唯一鍵，情緒評分管線、資料保留清理皆各自獨立，避免論壇雜訊污染既有新聞情緒品質。

-- ── forum_post（PTT 貼文本身，含情緒評分，§4.1）──────────────────────────
-- 一篇文章只存一列，不像 stock_news 依提及標的數複製 N 列（ADR-P7-04）：情緒評分是對整篇
-- 文章做的，提及哪些標的另由 forum_post_symbol 記錄。
CREATE TABLE IF NOT EXISTS forum_post (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(20) NOT NULL,                  -- 目前僅 'ptt_stock'（§3.2）
    post_key TEXT NOT NULL,                        -- PTT 的 M.xxx.A.xxx，穩定去重鍵（ADR-P7-05）
    url TEXT NOT NULL,                             -- 完整網址，供前端連結
    title TEXT NOT NULL,
    category VARCHAR(10),                          -- 標的/請益/心得/新聞/閒聊
    author VARCHAR(40),
    body_excerpt TEXT,                             -- 截斷後內文（截斷長度留給 P1 抓取器決定）
    push_count INTEGER NOT NULL DEFAULT 0,
    boo_count INTEGER NOT NULL DEFAULT 0,
    arrow_count INTEGER NOT NULL DEFAULT 0,
    posted_at TIMESTAMP NOT NULL,                  -- 文章真實發布時間
    effective_trade_date DATE NOT NULL,            -- 對齊交易日後的日期，比照 Phase4 ADR-P4-05 精神
    sentiment_score NUMERIC(4, 3),                 -- -1.000～1.000，NULL = 尚未評分
    sentiment_label VARCHAR(10),                   -- BULLISH / BEARISH / NEUTRAL
    sentiment_reason TEXT,                         -- LLM 評分理由，供人工稽核
    sentiment_engine VARCHAR(20),                  -- 評分引擎版本，供品質稽核
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source, post_key)
);

-- 依交易日查當日貼文：首頁摘要卡、排行表的主要查詢路徑
CREATE INDEX IF NOT EXISTS idx_forum_post_effective_date
    ON forum_post (effective_trade_date DESC);

-- 待評分佇列查詢（list_unscored()）：partial index 避免掃描已評分的大多數列
CREATE INDEX IF NOT EXISTS idx_forum_post_pending_sentiment
    ON forum_post (id) WHERE sentiment_score IS NULL;

-- ── forum_post_symbol（貼文與標的的關聯，§4.2）──────────────────────────
CREATE TABLE IF NOT EXISTS forum_post_symbol (
    post_id BIGINT NOT NULL REFERENCES forum_post(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL REFERENCES symbols(symbol) ON DELETE RESTRICT,
    matched_by VARCHAR(10) NOT NULL,               -- 'code'（股號比對）或 'name'（公司名稱比對）
    PRIMARY KEY (post_id, symbol)
);

-- 依標的聚合查詢（list_top_discussed() 的 JOIN 路徑）：複合主鍵 (post_id, symbol) 只覆蓋
-- 「先查 post_id」方向，「先查 symbol」方向需要額外索引
CREATE INDEX IF NOT EXISTS idx_forum_post_symbol_symbol
    ON forum_post_symbol (symbol, post_id);
