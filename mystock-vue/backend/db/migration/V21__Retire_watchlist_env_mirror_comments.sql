-- ============================================================
-- V21__Retire_watchlist_env_mirror_comments.sql
-- 撤回 ADR-02（.env 鏡像），見
-- docs/15.追蹤個股清單優化/追蹤與觀察名單整合_規劃書.md v1.7。
--
-- 無 schema 變更：is_crawl_enabled/source 欄位語意不變，只有「爬蟲抓取範圍怎麼被讀取」這件事
-- 從「Postgres 鏡像寫回 .env、爬蟲讀 .env」改成「爬蟲直接查 Postgres」。V12 當時下的
-- COMMENT ON TABLE/COLUMN 提到「鏡像寫回 .env」已不準確，這裡只更新註解文字，不改資料。
-- ============================================================

COMMENT ON TABLE portfolio_watchlist IS
    '個股追蹤與觀察清單（原「潛力股觀察名單」）。is_crawl_enabled=TRUE 的項目即爬蟲抓取範圍，'
    '為 config.get_target_stocks() 的唯一資料來源（2026-08-30 起不再鏡像寫回 .env 的 '
    'STOCK_CODES/US_STOCK_CODES）；target_price 為 NULL 代表純追蹤、不做到價提醒';
