-- ============================================================
-- V13__Add_slack_channel.sql
-- 新增 Slack 管道（Incoming Webhook，ADR-14 擴充性驗證點）
-- ============================================================

INSERT INTO notify_channel (channel_code, channel_name, status, capabilities) VALUES
  ('slack', 'Slack', 'disabled', '{"rich_text":false,"subject_line":false,"link_button":true,"attachment":false,"max_body_length":40000}')
ON CONFLICT (channel_code) DO NOTHING;
