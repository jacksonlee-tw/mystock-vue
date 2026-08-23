-- ============================================================
-- V12__Extend_watchlist_tracking.sql
-- 追蹤股票號碼（.env）與觀察名單（portfolio_watchlist）整合，見
-- docs/14.追蹤個股清單優化/追蹤與觀察名單整合_規劃書.md §4
--
-- 設計摘要：
--   - portfolio_watchlist 升級為系統唯一的個股清單（原「潛力股觀察名單」）。
--   - target_price 改為選填：有值＝觀察標的（算距目標／到價提醒），NULL＝純追蹤（只抓資料）。
--   - is_crawl_enabled=TRUE 的項目即爬蟲抓取範圍，由後端（services/tracking_service.py）鏡像寫回
--     .env 的 STOCK_CODES / US_STOCK_CODES；.env 仍是爬蟲/回補/掃描/腳本等既有同步消費者的讀取來源
--     （ADR-02：避免逼 8 處同步呼叫改綁 DB）。
--   - tag 以字典表＋關聯表正規化（ADR-04），不用 JSONB 陣列。
-- ============================================================

-- ── 1. 目標買進價改為選填（純追蹤項目沒有目標價）──────────────
--    原 CHECK (target_price > 0) 在值為 NULL 時求值為 UNKNOWN、視同通過，無需重建約束。
ALTER TABLE portfolio_watchlist ALTER COLUMN target_price DROP NOT NULL;

-- ── 2. 追蹤旗標與來源標記 ────────────────────────────────────
ALTER TABLE portfolio_watchlist
    ADD COLUMN IF NOT EXISTS is_crawl_enabled BOOLEAN     NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS source           VARCHAR(20) NOT NULL DEFAULT 'manual';
    -- source: manual | env_import | screener | alert | symbol_browser（供日後分析加入來源）

CREATE INDEX IF NOT EXISTS idx_portfolio_watchlist_crawl
    ON portfolio_watchlist (market, is_crawl_enabled);

COMMENT ON TABLE portfolio_watchlist IS
    '個股追蹤與觀察清單（原「潛力股觀察名單」）。is_crawl_enabled=TRUE 的項目即爬蟲抓取範圍，'
    '由後端鏡像寫回 .env 的 STOCK_CODES/US_STOCK_CODES；target_price 為 NULL 代表純追蹤、不做到價提醒';
COMMENT ON COLUMN portfolio_watchlist.note IS '追蹤原因／備註（選填）';
COMMENT ON COLUMN portfolio_watchlist.target_price IS '目標買進價（選填）；NULL 代表純追蹤，不計算距目標／到價提醒';
COMMENT ON COLUMN portfolio_watchlist.is_crawl_enabled IS '是否納入每日爬蟲抓取範圍（鏡像至 .env）；暫停抓取不會刪除本列 metadata';
COMMENT ON COLUMN portfolio_watchlist.source IS '加入來源：manual/env_import/screener/alert/symbol_browser，僅供分析用途';

-- ── 3. 自訂 tag ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS watchlist_tag (
    id         BIGSERIAL   PRIMARY KEY,
    name       VARCHAR(30) NOT NULL,
    color      VARCHAR(20) NOT NULL DEFAULT 'slate',   -- 前端色票 key，見 frontend useWatchlistTags.js
    sort_order INTEGER     NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 不分市場共用；以 LOWER(name) 唯一，避免「存股」「 存股 」「AI」「ai」重複建立
CREATE UNIQUE INDEX IF NOT EXISTS uq_watchlist_tag_name ON watchlist_tag (LOWER(name));

COMMENT ON TABLE watchlist_tag IS '追蹤與觀察名單的自訂標籤字典（跨市場共用，改名/改色一次對所有引用生效）';

CREATE TABLE IF NOT EXISTS watchlist_item_tag (
    watchlist_id BIGINT NOT NULL REFERENCES portfolio_watchlist (id) ON DELETE CASCADE,
    tag_id       BIGINT NOT NULL REFERENCES watchlist_tag (id)       ON DELETE CASCADE,
    PRIMARY KEY (watchlist_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_watchlist_item_tag_tag ON watchlist_item_tag (tag_id);

COMMENT ON TABLE watchlist_item_tag IS '清單項目 <-> tag 多對多關聯；刪除 tag 只移除關聯，不影響清單項目本身';
