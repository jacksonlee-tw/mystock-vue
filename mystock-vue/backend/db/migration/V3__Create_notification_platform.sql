-- ============================================================
-- V3__Create_notification_platform.sql
-- 整合訊息通知平台 — 新增 17 張表（不異動既有表）
-- ============================================================

-- ── 管道設定 ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notify_channel (
    channel_code        VARCHAR(32)     PRIMARY KEY,
    channel_name        VARCHAR(64)     NOT NULL,
    status              VARCHAR(20)     NOT NULL DEFAULT 'disabled'
                            CHECK (status IN ('enabled','disabled','misconfigured','circuit_open')),
    settings_enc        TEXT,           -- Fernet 密文（ADR-08）
    capabilities        JSONB           NOT NULL DEFAULT '{}',
    consecutive_failures INT            NOT NULL DEFAULT 0,
    circuit_open_until  TIMESTAMPTZ,
    last_health_at      TIMESTAMPTZ,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- 種入兩個管道（status=disabled，須管理者手動填入憑證後啟用）
INSERT INTO notify_channel (channel_code, channel_name, status, capabilities) VALUES
  ('email',    'Email',    'disabled', '{"rich_text":true,"subject_line":true,"link_button":false,"attachment":false,"max_body_length":100000}'),
  ('telegram', 'Telegram', 'disabled', '{"rich_text":false,"subject_line":false,"link_button":true,"attachment":false,"max_body_length":4096}')
ON CONFLICT (channel_code) DO NOTHING;

-- ── 收件人 ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notify_recipient (
    id              BIGSERIAL       PRIMARY KEY,
    recipient_code  VARCHAR(64)     NOT NULL UNIQUE,
    display_name    VARCHAR(128)    NOT NULL,
    status          VARCHAR(20)     NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','disabled')),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- ── 收件端點 ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notify_endpoint (
    id                  BIGSERIAL       PRIMARY KEY,
    endpoint_code       VARCHAR(64)     NOT NULL UNIQUE,
    channel_code        VARCHAR(32)     NOT NULL REFERENCES notify_channel(channel_code),
    recipient_id        BIGINT          REFERENCES notify_recipient(id),
    endpoint_scope      VARCHAR(16)     NOT NULL DEFAULT 'personal'
                            CHECK (endpoint_scope IN ('personal','shared')),
    address             VARCHAR(512)    NOT NULL,
    verify_status       VARCHAR(20)     NOT NULL DEFAULT 'pending'
                            CHECK (verify_status IN ('pending','verified')),
    status              VARCHAR(20)     NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active','disabled','unsubscribed')),
    delivery_mode       VARCHAR(20)     NOT NULL DEFAULT 'realtime'
                            CHECK (delivery_mode IN ('realtime','digest','critical_only')),
    quiet_start         TIME,
    quiet_end           TIME,
    timezone            VARCHAR(64)     NOT NULL DEFAULT 'Asia/Taipei',
    daily_limit         INT             NOT NULL DEFAULT 30,
    digest_send_time    TIME,
    pause_until         TIMESTAMPTZ,
    fallback_endpoint_id BIGINT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_notify_endpoint_scope CHECK (
        (endpoint_scope = 'personal' AND recipient_id IS NOT NULL) OR
        (endpoint_scope = 'shared'   AND recipient_id IS NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_notify_endpoint_channel_address
    ON notify_endpoint (channel_code, address);

ALTER TABLE notify_endpoint
    ADD CONSTRAINT fk_notify_endpoint_fallback
    FOREIGN KEY (fallback_endpoint_id) REFERENCES notify_endpoint(id)
    DEFERRABLE INITIALLY DEFERRED;

-- ── 收件群組 ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notify_group (
    id          BIGSERIAL   PRIMARY KEY,
    group_code  VARCHAR(64) NOT NULL UNIQUE,
    group_name  VARCHAR(128) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS notify_group_member (
    group_id        BIGINT  NOT NULL REFERENCES notify_group(id) ON DELETE CASCADE,
    recipient_id    BIGINT  NOT NULL REFERENCES notify_recipient(id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, recipient_id)
);

-- ── 訂閱規則 ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notify_subscription (
    id                  BIGSERIAL   PRIMARY KEY,
    rule_code           VARCHAR(64) NOT NULL UNIQUE,
    rule_name           VARCHAR(128) NOT NULL,
    event_type          VARCHAR(64) NOT NULL,
    filter_conditions   JSONB       NOT NULL DEFAULT '{}',
    target_group_id     BIGINT      REFERENCES notify_group(id),
    target_recipient_id BIGINT      REFERENCES notify_recipient(id),
    target_endpoint_id  BIGINT      REFERENCES notify_endpoint(id),
    status              VARCHAR(20) NOT NULL DEFAULT 'enabled'
                            CHECK (status IN ('enabled','disabled')),
    priority            INT         NOT NULL DEFAULT 100,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_notify_subscription_single_target CHECK (
        (target_group_id     IS NOT NULL)::int
      + (target_recipient_id IS NOT NULL)::int
      + (target_endpoint_id  IS NOT NULL)::int = 1
    )
);

-- ── 事件 ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notify_event (
    id              BIGSERIAL       PRIMARY KEY,
    event_uid       UUID            NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    idempotency_key VARCHAR(256)    NOT NULL,
    event_type      VARCHAR(64)     NOT NULL,
    severity        VARCHAR(20)     NOT NULL CHECK (severity IN ('info','warning','critical')),
    source          VARCHAR(64)     NOT NULL,
    occurred_at     TIMESTAMPTZ     NOT NULL,
    received_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    payload         JSONB           NOT NULL DEFAULT '{}',
    routing_facts   JSONB           NOT NULL DEFAULT '{}',
    routed_status   VARCHAR(20)     NOT NULL DEFAULT 'pending'
                        CHECK (routed_status IN ('pending','routed','no_match','invalid'))
);

CREATE INDEX IF NOT EXISTS idx_notify_event_key  ON notify_event (idempotency_key);
CREATE INDEX IF NOT EXISTS idx_notify_event_type ON notify_event (event_type, received_at DESC);

-- ── 訊息單（Outbox） ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notify_message (
    id                  BIGSERIAL       PRIMARY KEY,
    message_code        VARCHAR(128)    NOT NULL UNIQUE,
    event_id            BIGINT          NOT NULL REFERENCES notify_event(id),
    endpoint_id         BIGINT          NOT NULL REFERENCES notify_endpoint(id),
    channel_code        VARCHAR(32)     NOT NULL,
    idempotency_key     VARCHAR(256)    NOT NULL,
    priority            SMALLINT        NOT NULL DEFAULT 10,
    status              VARCHAR(30)     NOT NULL DEFAULT 'pending'
                            CHECK (status IN (
                                'pending','sending','sent','failed','dead',
                                'skipped_duplicate','throttled','deferred',
                                'digest_pending','digested','skipped_paused'
                            )),
    subject             TEXT,
    body                TEXT            NOT NULL DEFAULT '',
    scheduled_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    attempt_count       INT             NOT NULL DEFAULT 0,
    next_retry_at       TIMESTAMPTZ,
    claimed_at          TIMESTAMPTZ,
    claimed_by          VARCHAR(64),
    sent_at             TIMESTAMPTZ,
    digest_message_id   BIGINT,
    last_failure_kind   VARCHAR(32),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_notify_message_dedup
    ON notify_message (idempotency_key, endpoint_id);

CREATE INDEX IF NOT EXISTS idx_notify_message_queue
    ON notify_message (priority ASC, scheduled_at ASC)
    WHERE status IN ('pending','failed');

CREATE INDEX IF NOT EXISTS idx_notify_message_lookup
    ON notify_message (created_at DESC, status, channel_code);

ALTER TABLE notify_message
    ADD CONSTRAINT fk_notify_message_digest
    FOREIGN KEY (digest_message_id) REFERENCES notify_message(id)
    DEFERRABLE INITIALLY DEFERRED;

-- ── 投遞紀錄 ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notify_delivery_log (
    id                  BIGSERIAL   PRIMARY KEY,
    message_id          BIGINT      NOT NULL REFERENCES notify_message(id),
    attempt_no          INT         NOT NULL,
    result              VARCHAR(30) NOT NULL CHECK (result IN ('success','retryable_failure','permanent_failure','skipped')),
    failure_kind        VARCHAR(32),
    failure_reason      TEXT,
    provider_message_id VARCHAR(256),
    latency_ms          INT,
    attempted_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notify_delivery_log_msg
    ON notify_delivery_log (message_id, attempt_no);

-- ── 訊息模板 ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notify_template (
    id              BIGSERIAL   PRIMARY KEY,
    template_code   VARCHAR(128) NOT NULL UNIQUE,
    event_type      VARCHAR(64) NOT NULL,
    channel_code    VARCHAR(32) NOT NULL REFERENCES notify_channel(channel_code),
    title_format    TEXT,
    body_format     TEXT        NOT NULL DEFAULT '',
    body_kind       VARCHAR(16) NOT NULL DEFAULT 'text'
                        CHECK (body_kind IN ('text','html','markdown')),
    is_default      BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_notify_template_pair
    ON notify_template (event_type, channel_code);

-- ── 綁定/驗證 Token ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notify_binding_token (
    id              BIGSERIAL   PRIMARY KEY,
    token_digest    CHAR(64)    NOT NULL UNIQUE,
    purpose         VARCHAR(32) NOT NULL CHECK (purpose IN ('email_verify','telegram_bind')),
    channel_code    VARCHAR(32) NOT NULL,
    endpoint_id     BIGINT      REFERENCES notify_endpoint(id),
    recipient_id    BIGINT      REFERENCES notify_recipient(id),
    expires_at      TIMESTAMPTZ NOT NULL,
    used_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 自助連結 Token ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notify_self_service_token (
    id              BIGSERIAL   PRIMARY KEY,
    token_digest    CHAR(64)    NOT NULL UNIQUE,
    recipient_id    BIGINT      NOT NULL REFERENCES notify_recipient(id),
    status          VARCHAR(16) NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','revoked')),
    revoked_at      TIMESTAMPTZ,
    last_used_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_notify_sst_active
    ON notify_self_service_token (recipient_id) WHERE status = 'active';

-- ── 收件人偏好 ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notify_recipient_preference (
    recipient_id                BIGINT  PRIMARY KEY REFERENCES notify_recipient(id),
    allowed_markets             JSONB   NOT NULL DEFAULT '["tw","us"]',
    allowed_strengths           JSONB   NOT NULL DEFAULT '["strong","moderate","weak"]',
    allowed_signal_types        JSONB   NOT NULL DEFAULT '["BUY","SELL","WARNING"]',
    allowed_strategy_categories JSONB   NOT NULL DEFAULT '["technical","chip","fundamental"]',
    watch_symbols               JSONB,
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 偏好異動稽核 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notify_preference_audit (
    id              BIGSERIAL   PRIMARY KEY,
    recipient_id    BIGINT      NOT NULL REFERENCES notify_recipient(id),
    actor           VARCHAR(64) NOT NULL DEFAULT 'self',
    change_summary  JSONB       NOT NULL,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 每日用量計數 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notify_quota_usage (
    scope       VARCHAR(32)  NOT NULL,
    scope_key   VARCHAR(128) NOT NULL,
    usage_date  DATE         NOT NULL,
    used_count  INT          NOT NULL DEFAULT 0,
    PRIMARY KEY (scope, scope_key, usage_date)
);

-- ── 告警防遞迴抑制 ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notify_suppression (
    cooldown_key        VARCHAR(128) PRIMARY KEY,
    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    occurrence_count    INT         NOT NULL DEFAULT 1,
    cooldown_until      TIMESTAMPTZ NOT NULL
);

-- ── 管理端操作稽核 ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notify_admin_audit (
    id          BIGSERIAL   PRIMARY KEY,
    actor       VARCHAR(64) NOT NULL DEFAULT 'owner',
    action      VARCHAR(128) NOT NULL,
    target      VARCHAR(256),
    result      VARCHAR(16) NOT NULL CHECK (result IN ('success','failure')),
    detail      JSONB,
    acted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
