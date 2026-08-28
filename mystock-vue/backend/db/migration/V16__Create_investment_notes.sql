-- ============================================================
-- V16__Create_investment_notes.sql
-- 個人投資記帳－投資筆記模組（docs/8.個人投資記帳功能/個人投資筆記.md）
--
-- 記錄投資決策、研究心得、市場事件與事後檢討，跟交易紀錄／持股計算／觀察名單完全解耦
-- （R3：不寫入既有欄位的 note）。同一 note_date 依 sequence_no 從 1 起算，供同日多筆時保留
-- 建立順序；market/symbol 為邏輯關聯、不建 FK，退市或代號變更後仍可保留歷史筆記原文。
-- ============================================================

-- ── 投資筆記主表 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investment_note (
    id              BIGSERIAL       PRIMARY KEY,
    note_date       DATE            NOT NULL DEFAULT CURRENT_DATE,
    sequence_no     INTEGER         NOT NULL CHECK (sequence_no > 0),
    subject         VARCHAR(200)    NOT NULL CHECK (btrim(subject) <> ''),
    content         TEXT            NOT NULL CHECK (btrim(content) <> ''),
    market          VARCHAR(10),
    symbol          VARCHAR(20),
    symbol_name     VARCHAR(100),
    status          VARCHAR(10)     NOT NULL DEFAULT 'published'
        CHECK (status IN ('published', 'draft', 'archived')),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_investment_note_date_sequence UNIQUE (note_date, sequence_no),
    CONSTRAINT ck_investment_note_symbol_pair CHECK (
        (market IS NULL AND symbol IS NULL) OR
        (market IS NOT NULL AND symbol IS NOT NULL)
    ),
    CONSTRAINT ck_investment_note_market CHECK (market IS NULL OR market IN ('tw', 'us'))
);

CREATE INDEX IF NOT EXISTS idx_investment_note_date
    ON investment_note (note_date DESC, sequence_no DESC);
CREATE INDEX IF NOT EXISTS idx_investment_note_symbol
    ON investment_note (market, symbol, note_date DESC);
CREATE INDEX IF NOT EXISTS idx_investment_note_status
    ON investment_note (status, note_date DESC);

COMMENT ON COLUMN investment_note.sequence_no IS
    '同一 note_date 從 1 起算；刪除中間筆記後不得重排其他筆記的流水號（R1）';
COMMENT ON COLUMN investment_note.symbol_name IS
    '建立／更新當下的股票名稱快照；標的退市或改名後，歷史筆記仍保留當時名稱';

-- ── 自訂標籤字典 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investment_note_tag (
    id          BIGSERIAL       PRIMARY KEY,
    name        VARCHAR(30)     NOT NULL,
    color       VARCHAR(20)     NOT NULL DEFAULT 'slate',
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- 名稱不分大小寫唯一（設計文件 §3.2）
CREATE UNIQUE INDEX IF NOT EXISTS uq_investment_note_tag_name
    ON investment_note_tag (LOWER(name));

-- ── 筆記 <-> 標籤關聯 ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investment_note_tag_link (
    note_id BIGINT NOT NULL REFERENCES investment_note(id) ON DELETE CASCADE,
    tag_id  BIGINT NOT NULL REFERENCES investment_note_tag(id) ON DELETE CASCADE,
    PRIMARY KEY (note_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_investment_note_tag_link_tag
    ON investment_note_tag_link (tag_id, note_id);
