-- V14__Create_ai_analysis_tables.sql
-- 依據《AI 技術分析報告 系統開發規格書》(v3.1，docs/16.AI技術分析/AI技術分析規劃.md) §5 建立三張表
-- 唯一鍵 (market_type, symbol, trade_date) 是「同一標的同一交易日只呼叫一次 LLM」的實體保證

-- ── 表 1：AI 技術分析報告（§5.3）─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_analysis_report (
    id                BIGSERIAL PRIMARY KEY,
    -- ── 唯一鍵三欄（ADR-AI-13、ADR-AI-16）──────────────────────
    symbol            VARCHAR(20)  NOT NULL,
    market_type       VARCHAR(10)  NOT NULL,
    trade_date        DATE         NOT NULL,
    -- ── 執行狀態（併發佔位用，§5.8）─────────────────────────────
    status            VARCHAR(10)  NOT NULL DEFAULT 'running',
    -- ── 標的與模型中繼資料 ──────────────────────────────────────
    stock_name        VARCHAR(100),
    provider          VARCHAR(20)  NOT NULL,
    model             VARCHAR(60),
    -- ── 產生報告時的圖表視角（不存圖片本身，ADR-AI-15）──────────
    chart_period      VARCHAR(10),
    chart_months      INTEGER,
    chart_start_date  DATE,
    chart_end_date    DATE,
    -- ── 結構化報告內容（§4.5）───────────────────────────────────
    verdict           VARCHAR(10),
    headline          TEXT,
    support_levels    JSONB,
    resistance_levels JSONB,
    stop_loss         NUMERIC(15, 4),
    report_markdown   TEXT,
    confidence        VARCHAR(10),
    -- ── 稽核 ────────────────────────────────────────────────────
    -- 注意：token 與耗時「不」放這裡，一律記在 ai_llm_execution（ADR-AI-17）
    quant_summary     JSONB,
    truncated         BOOLEAN      NOT NULL DEFAULT FALSE,
    error_code        VARCHAR(40),
    generated_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 每檔每交易日僅一列（ADR-AI-16 的實體保證；ON CONFLICT 依賴此索引）
CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_report_daily
    ON ai_analysis_report (market_type, symbol, trade_date);

-- 歷史列表：預設依產生時間新到舊
CREATE INDEX IF NOT EXISTS idx_ai_report_recent
    ON ai_analysis_report (generated_at DESC);

-- 單一標的的歷史軌跡
CREATE INDEX IF NOT EXISTS idx_ai_report_symbol_date
    ON ai_analysis_report (market_type, symbol, trade_date DESC);

-- 依趨勢研判篩選
CREATE INDEX IF NOT EXISTS idx_ai_report_verdict
    ON ai_analysis_report (trade_date DESC, verdict);

-- 回收卡住的 running 列（§5.8）
CREATE INDEX IF NOT EXISTS idx_ai_report_status
    ON ai_analysis_report (status, updated_at);


-- ── 表 2：LLM 呼叫執行紀錄（參考 dify_workflow_execution，轉為 PostgreSQL，§5.5）──
-- 粒度：一次呼叫一列。成功與失敗一視同仁，失敗同樣可能已計費（ADR-AI-17）
CREATE TABLE IF NOT EXISTS ai_llm_execution (
    id                  BIGSERIAL PRIMARY KEY,
    execution_uuid      UUID         NOT NULL DEFAULT gen_random_uuid(),
    -- 關聯報告；報告被刪除時保留本列（成本紀錄不可消失）
    report_id           BIGINT       REFERENCES ai_analysis_report(id) ON DELETE SET NULL,
    -- ── 呼叫對象 ────────────────────────────────────────────────
    provider            VARCHAR(20)  NOT NULL,              -- claude | gemini
    model               VARCHAR(60)  NOT NULL,              -- 實際使用的模型 ID
    call_mode           VARCHAR(20)  NOT NULL DEFAULT 'blocking',  -- blocking | streaming
    prompt_version      VARCHAR(20),                        -- ai/prompt.py 的常數，改提示詞時手動遞增
    -- ── 標的快照（報告被刪除後仍可統計）────────────────────────
    symbol              VARCHAR(20),
    market_type         VARCHAR(10),
    trade_date          DATE,
    -- ── 執行狀態 ────────────────────────────────────────────────
    status              VARCHAR(20)  NOT NULL DEFAULT 'pending',   -- pending | succeeded | failed
    attempt_no          INTEGER      NOT NULL DEFAULT 1,   -- 該報告的第幾次嘗試
    stop_reason         VARCHAR(30),                        -- end_turn | max_tokens | refusal
    error_code          VARCHAR(40),                        -- 對應 §4.7 的錯誤碼
    error_message       TEXT,
    -- ── 請求／回應中繼資料（不含 prompt 全文與圖片，見 §8.2）──
    request_meta        JSONB,                              -- max_tokens、effort、圖片尺寸等
    response_meta        JSONB,                             -- 回應中繼欄位
    provider_request_id VARCHAR(100),                       -- Anthropic 的 request id，回報問題用
    -- ── 用量與成本（本模組的成本唯一事實來源）──────────────────
    input_tokens        INTEGER,
    output_tokens        INTEGER,
    cache_read_tokens    INTEGER,
    cache_write_tokens   INTEGER,
    total_tokens        INTEGER GENERATED ALWAYS AS
                        (COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)) STORED,
    image_bytes          INTEGER,                            -- 送出的 K 線圖大小
    estimated_cost_usd   NUMERIC(12, 6),                     -- 依 §10 的模型定價於寫入時計算
    -- ── 時間 ────────────────────────────────────────────────────
    elapsed_ms           INTEGER,
    started_at           TIMESTAMP,
    completed_at         TIMESTAMP,
    -- ── 其他 ────────────────────────────────────────────────────
    is_dry_run           BOOLEAN      NOT NULL DEFAULT FALSE, -- 開發試跑，排除於成本統計之外
    submitted_by         VARCHAR(100) NOT NULL DEFAULT 'owner',
    created_at           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_exec_uuid
    ON ai_llm_execution (execution_uuid);
CREATE INDEX IF NOT EXISTS idx_ai_exec_report
    ON ai_llm_execution (report_id);
CREATE INDEX IF NOT EXISTS idx_ai_exec_status
    ON ai_llm_execution (status);
CREATE INDEX IF NOT EXISTS idx_ai_exec_created
    ON ai_llm_execution (created_at DESC);
-- 用量統計：依模型分組看花費
CREATE INDEX IF NOT EXISTS idx_ai_exec_provider_model
    ON ai_llm_execution (provider, model, created_at DESC);
-- 單一標的的呼叫軌跡
CREATE INDEX IF NOT EXISTS idx_ai_exec_symbol
    ON ai_llm_execution (market_type, symbol, trade_date DESC);
-- 成本報表：排除試跑後依時間彙總
CREATE INDEX IF NOT EXISTS idx_ai_exec_cost
    ON ai_llm_execution (is_dry_run, created_at DESC);


-- ── 表 3：系統活動事件紀錄（參考 cm_activity_log，轉為 PostgreSQL，§5.6）──
-- 粒度：一次操作一列。本次只接 AI 模組事件，code 以 AI_ 前綴區隔（ADR-AI-18）
CREATE TABLE IF NOT EXISTS activity_log (
    id           BIGSERIAL PRIMARY KEY,
    code         VARCHAR(30)   NOT NULL,               -- 事件代碼
    view_id      VARCHAR(60),                          -- 觸發來源畫面
    detail       VARCHAR(1024),                        -- 事件描述
    success      BOOLEAN,                              -- 成功與否
    rel_id       BIGINT,                               -- 關聯業務主鍵（此處為 ai_analysis_report.id）
    comments     VARCHAR(1024),                        -- 補充說明（失敗原因、閘門代碼等）
    created_by   VARCHAR(50)   NOT NULL DEFAULT 'owner',  -- 本系統為單一擁有者，無使用者表
    created_date TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_activity_log_code
    ON activity_log (code);
CREATE INDEX IF NOT EXISTS idx_activity_log_created_by
    ON activity_log (created_by);
CREATE INDEX IF NOT EXISTS idx_activity_log_created_date
    ON activity_log (created_date DESC);
-- 查「某份報告發生過哪些事」
CREATE INDEX IF NOT EXISTS idx_activity_log_rel
    ON activity_log (code, rel_id);
