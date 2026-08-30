-- ============================================================
-- V19__Create_industry_chain_tables.sql
-- 產業鏈知識圖譜與輪動模型（docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §5）
--
-- 讀取／查詢面（圖 API、BFS、CCF 快取）需要 PostgreSQL，且不受 DATA_SOURCE 影響
-- （ADR-IC-01）；寫入面採「JSON 快照優先 + Postgres best-effort 雙寫」（ADR-IC-09）。
-- 不建 symbols 外鍵，理由與 V6 symbol_industry 相同：symbols 主要由台股代碼母體填充，
-- 加外鍵會讓尚未存在於 symbols 的標的寫入失敗。
-- ============================================================

-- ── 表 1：產業鏈上下游關聯邊（§5.2）───────────────────────────
CREATE TABLE IF NOT EXISTS industry_chain_edges (
    id                  BIGSERIAL      PRIMARY KEY,
    -- 對應 industry_chain_config/industry_chains.yaml 的 chain_id（如 "ai_server"）；
    -- 不建 FK（YAML 不在 DB 內），有效性由應用層核對
    chain_id            VARCHAR(50)    NOT NULL,
    upstream_symbol     VARCHAR(20)    NOT NULL,
    downstream_symbol   VARCHAR(20)    NOT NULL,
    -- 現行只會是 'tw'（見規格書 §1.3），欄位保留供日後跨市場擴充
    upstream_market     VARCHAR(10)    NOT NULL,
    downstream_market   VARCHAR(10)    NOT NULL,
    -- 1 = 直接上游/下游，2 = 次一層，以此類推
    relation_tier       SMALLINT       NOT NULL,
    component_type      VARCHAR(50),
    -- llm_gemini / llm_claude / moneydj / mops_footnote / manual
    source              VARCHAR(20)    NOT NULL,
    is_verified         BOOLEAN        NOT NULL DEFAULT FALSE,
    -- 供應鏈關係變動時軟刪除，不物理刪除（保留歷史稽核）
    is_active           BOOLEAN        NOT NULL DEFAULT TRUE,
    first_seen_date     DATE,
    last_confirmed_date DATE,
    -- 彈性擴充欄位，比照 daily_stock_data.market_specific_data 既有慣例（V1 遷移）：
    -- schema 尚不穩定或來源各異的補充資訊放這裡，僅供顯示與稽核，不得作為篩選依據
    extra_data          JSONB,
    created_at          TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 同一條鏈的同一組上下游只保留一列（AC-IC-1：重複匯入不產生重複列，ON CONFLICT 依賴此索引）
CREATE UNIQUE INDEX IF NOT EXISTS uq_industry_chain_edge
    ON industry_chain_edges (chain_id, upstream_symbol, downstream_symbol);

-- 下游點火後 BFS 向上游查詢
CREATE INDEX IF NOT EXISTS idx_chain_downstream
    ON industry_chain_edges (downstream_symbol, is_active);
-- 上游標的反查其下游
CREATE INDEX IF NOT EXISTS idx_chain_upstream
    ON industry_chain_edges (upstream_symbol, is_active);

COMMENT ON COLUMN industry_chain_edges.extra_data IS
    '彈性擴充欄位（比照 daily_stock_data.market_specific_data），例如 llm_model／llm_evidence／
    evidence_url／concept_tag_match，僅供顯示與稽核，不得作為 §4.3 篩選邏輯的判斷依據';


-- ── 表 2：領先—落後量化檢定快取（§5.3，FR-8）───────────────────
CREATE TABLE IF NOT EXISTS industry_chain_lead_lag_cache (
    id                       BIGSERIAL   PRIMARY KEY,
    edge_id                  BIGINT      NOT NULL REFERENCES industry_chain_edges(id),
    -- 計算所用的歷史區間
    window_start             DATE        NOT NULL,
    window_end               DATE        NOT NULL,
    peak_lag_days            SMALLINT,
    correlation_coefficient  NUMERIC(6, 4),
    -- 參與計算的交易日數，前端／使用者判斷可信度用（FR-7a：< IC_MIN_SAMPLE_SIZE 不得寫入本表）
    sample_size              INTEGER     NOT NULL,
    computed_at              TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 同一條邊在同一個計算截止日只保留一筆，重算時 upsert
CREATE UNIQUE INDEX IF NOT EXISTS uq_lead_lag_edge_window
    ON industry_chain_lead_lag_cache (edge_id, window_end);

CREATE INDEX IF NOT EXISTS idx_lead_lag_edge
    ON industry_chain_lead_lag_cache (edge_id);
