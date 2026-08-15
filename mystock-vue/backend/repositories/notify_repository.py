"""
repositories/notify_repository.py
整合訊息通知平台唯一 SQL 入口（§5.1，ADR-13）
所有對 notify_* 表的讀寫都必須經由此 Repository，
不得在 notify/ 套件內直接操作 sqlalchemy session（鐵則 R3）
"""
from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime, date, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("mystock-backend")


class NotifyRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    @property
    def session(self) -> AsyncSession:
        """供極少數需要沿用同一交易開另一個 Repository 實例的呼叫端使用
        （例如 notify/health_probe.py 的 report_delivery_dead()）。"""
        return self._s

    # ────────────────────────────────────────────────────────
    # 管道
    # ────────────────────────────────────────────────────────
    async def list_channels(self) -> list[dict]:
        result = await self._s.execute(text("SELECT * FROM notify_channel ORDER BY channel_code"))
        return [dict(r) for r in result.mappings()]

    async def get_channel(self, channel_code: str) -> dict | None:
        result = await self._s.execute(
            text("SELECT * FROM notify_channel WHERE channel_code = :code"),
            {"code": channel_code}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def update_channel(self, channel_code: str, updates: dict) -> None:
        set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
        await self._s.execute(
            text(f"UPDATE notify_channel SET {set_clauses}, updated_at = NOW() WHERE channel_code = :channel_code"),
            {**updates, "channel_code": channel_code}
        )

    async def increment_channel_failures(self, channel_code: str) -> None:
        from notify.channel_config import open_circuit_until
        result = await self._s.execute(
            text("SELECT consecutive_failures FROM notify_channel WHERE channel_code = :code"),
            {"code": channel_code}
        )
        row = result.mappings().first()
        if not row:
            return
        failures = (row["consecutive_failures"] or 0) + 1
        open_until = open_circuit_until(failures)
        status = "circuit_open" if open_until else None

        updates = {"consecutive_failures": failures}
        if open_until:
            updates["circuit_open_until"] = open_until  # TIMESTAMPTZ：需原生 datetime
            updates["status"] = "circuit_open"
        await self.update_channel(channel_code, updates)

    async def reset_channel_failures(self, channel_code: str) -> None:
        await self.update_channel(channel_code, {"consecutive_failures": 0, "circuit_open_until": None})

    async def set_channel_misconfigured(self, channel_code: str) -> None:
        await self.update_channel(channel_code, {"status": "misconfigured"})

    # ────────────────────────────────────────────────────────
    # 收件人
    # ────────────────────────────────────────────────────────
    async def list_recipients(self) -> list[dict]:
        result = await self._s.execute(text("SELECT * FROM notify_recipient ORDER BY id"))
        return [dict(r) for r in result.mappings()]

    async def get_recipient_by_code(self, recipient_code: str) -> dict | None:
        result = await self._s.execute(
            text("SELECT * FROM notify_recipient WHERE recipient_code = :code"),
            {"code": recipient_code}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def create_recipient(self, data: dict) -> int:
        result = await self._s.execute(
            text("""
                INSERT INTO notify_recipient (recipient_code, display_name, status)
                VALUES (:recipient_code, :display_name, :status)
                RETURNING id
            """),
            data
        )
        await self._s.flush()
        return result.scalar()

    async def get_recipient(self, recipient_id: int) -> dict | None:
        result = await self._s.execute(
            text("SELECT * FROM notify_recipient WHERE id = :id"),
            {"id": recipient_id}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def update_recipient(self, recipient_id: int, updates: dict) -> None:
        set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
        await self._s.execute(
            text(f"UPDATE notify_recipient SET {set_clauses}, updated_at = NOW() WHERE id = :id"),
            {**updates, "id": recipient_id}
        )

    async def list_recipients_with_groups(self) -> list[dict]:
        """收件人清單 + 所屬群組名稱（管理介面用，§9.2 對照 recipients.html）"""
        result = await self._s.execute(text("""
            SELECT r.*,
                   COALESCE(
                       (SELECT array_agg(g.group_name) FROM notify_group_member gm
                        JOIN notify_group g ON g.id = gm.group_id
                        WHERE gm.recipient_id = r.id),
                       ARRAY[]::text[]
                   ) AS group_names
            FROM notify_recipient r
            ORDER BY r.id
        """))
        return [dict(r) for r in result.mappings()]

    # ────────────────────────────────────────────────────────
    # 端點
    # ────────────────────────────────────────────────────────
    async def get_endpoint(self, endpoint_id: int) -> dict | None:
        result = await self._s.execute(
            text("SELECT * FROM notify_endpoint WHERE id = :id"),
            {"id": endpoint_id}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def get_endpoint_by_code(self, endpoint_code: str) -> dict | None:
        result = await self._s.execute(
            text("SELECT * FROM notify_endpoint WHERE endpoint_code = :code"),
            {"code": endpoint_code}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def list_endpoints_for_recipient(self, recipient_id: int) -> list[dict]:
        result = await self._s.execute(
            text("""
                SELECT * FROM notify_endpoint
                WHERE recipient_id = :rid AND status != 'unsubscribed'
                ORDER BY id
            """),
            {"rid": recipient_id}
        )
        return [dict(r) for r in result.mappings()]

    async def create_endpoint(self, data: dict) -> int:
        result = await self._s.execute(
            text("""
                INSERT INTO notify_endpoint (
                    endpoint_code, channel_code, recipient_id, endpoint_scope,
                    address, verify_status, status, delivery_mode,
                    quiet_start, quiet_end, timezone, daily_limit,
                    digest_send_time, fallback_endpoint_id
                ) VALUES (
                    :endpoint_code, :channel_code, :recipient_id, :endpoint_scope,
                    :address, :verify_status, :status, :delivery_mode,
                    :quiet_start, :quiet_end, :timezone, :daily_limit,
                    :digest_send_time, :fallback_endpoint_id
                ) RETURNING id
            """),
            data
        )
        await self._s.flush()
        return result.scalar()

    async def update_endpoint(self, endpoint_id: int, updates: dict) -> None:
        set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
        await self._s.execute(
            text(f"UPDATE notify_endpoint SET {set_clauses}, updated_at = NOW() WHERE id = :id"),
            {**updates, "id": endpoint_id}
        )

    async def get_endpoint_by_address(self, channel_code: str, address: str) -> dict | None:
        """同一管道下同一收件位址是否已存在（§5.2 唯一性；同一 Telegram 對話只能有一個有效端點）"""
        result = await self._s.execute(
            text("SELECT * FROM notify_endpoint WHERE channel_code = :cc AND address = :addr"),
            {"cc": channel_code, "addr": address}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def list_shared_endpoints(self) -> list[dict]:
        result = await self._s.execute(
            text("SELECT * FROM notify_endpoint WHERE endpoint_scope = 'shared' ORDER BY id")
        )
        return [dict(r) for r in result.mappings()]

    async def list_all_endpoints(self) -> list[dict]:
        result = await self._s.execute(text("SELECT * FROM notify_endpoint ORDER BY id"))
        return [dict(r) for r in result.mappings()]

    # ────────────────────────────────────────────────────────
    # 群組
    # ────────────────────────────────────────────────────────
    async def list_groups(self) -> list[dict]:
        result = await self._s.execute(text("SELECT * FROM notify_group ORDER BY id"))
        return [dict(r) for r in result.mappings()]

    async def list_group_members(self, group_id: int) -> list[dict]:
        result = await self._s.execute(
            text("SELECT * FROM notify_group_member WHERE group_id = :gid"),
            {"gid": group_id}
        )
        return [dict(r) for r in result.mappings()]

    async def get_group_by_code(self, group_code: str) -> dict | None:
        result = await self._s.execute(
            text("SELECT * FROM notify_group WHERE group_code = :code"),
            {"code": group_code}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def create_group(self, data: dict) -> int:
        result = await self._s.execute(
            text("INSERT INTO notify_group (group_code, group_name) VALUES (:group_code, :group_name) RETURNING id"),
            data
        )
        await self._s.flush()
        return result.scalar()

    async def add_group_member(self, group_id: int, recipient_id: int) -> None:
        await self._s.execute(
            text("""
                INSERT INTO notify_group_member (group_id, recipient_id)
                VALUES (:gid, :rid) ON CONFLICT DO NOTHING
            """),
            {"gid": group_id, "rid": recipient_id}
        )

    async def remove_group_member(self, group_id: int, recipient_id: int) -> None:
        await self._s.execute(
            text("DELETE FROM notify_group_member WHERE group_id = :gid AND recipient_id = :rid"),
            {"gid": group_id, "rid": recipient_id}
        )

    async def list_groups_with_members(self) -> list[dict]:
        groups = await self.list_groups()
        for g in groups:
            members = await self._s.execute(
                text("""
                    SELECT r.id, r.recipient_code, r.display_name FROM notify_group_member gm
                    JOIN notify_recipient r ON r.id = gm.recipient_id
                    WHERE gm.group_id = :gid
                """),
                {"gid": g["id"]}
            )
            g["members"] = [dict(m) for m in members.mappings()]
        return groups

    # ────────────────────────────────────────────────────────
    # 訂閱規則
    # ────────────────────────────────────────────────────────
    async def list_subscriptions_by_event_type(self, event_type: str) -> list[dict]:
        result = await self._s.execute(
            text("""
                SELECT * FROM notify_subscription
                WHERE status = 'enabled' AND event_type = :et
                ORDER BY priority ASC, id ASC
            """),
            {"et": event_type}
        )
        return [dict(r) for r in result.mappings()]

    async def list_all_subscriptions(self) -> list[dict]:
        result = await self._s.execute(text("SELECT * FROM notify_subscription ORDER BY priority ASC, id ASC"))
        return [dict(r) for r in result.mappings()]

    async def create_subscription(self, data: dict) -> int:
        payload = {**data, "filter_conditions": json.dumps(data.get("filter_conditions") or {})}
        result = await self._s.execute(
            text("""
                INSERT INTO notify_subscription (
                    rule_code, rule_name, event_type, filter_conditions,
                    target_group_id, target_recipient_id, target_endpoint_id,
                    status, priority
                ) VALUES (
                    :rule_code, :rule_name, :event_type, :filter_conditions,
                    :target_group_id, :target_recipient_id, :target_endpoint_id,
                    :status, :priority
                ) RETURNING id
            """),
            payload
        )
        await self._s.flush()
        return result.scalar()

    async def get_subscription_by_code(self, rule_code: str) -> dict | None:
        result = await self._s.execute(
            text("SELECT * FROM notify_subscription WHERE rule_code = :code"),
            {"code": rule_code}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def update_subscription(self, sub_id: int, updates: dict) -> None:
        payload = dict(updates)
        if isinstance(payload.get("filter_conditions"), (dict, list)):
            payload["filter_conditions"] = json.dumps(payload["filter_conditions"])  # JSONB：需先序列化為字串
        set_clauses = ", ".join(f"{k} = :{k}" for k in payload)
        await self._s.execute(
            text(f"UPDATE notify_subscription SET {set_clauses}, updated_at = NOW() WHERE id = :id"),
            {**payload, "id": sub_id}
        )

    # ────────────────────────────────────────────────────────
    # 事件
    # ────────────────────────────────────────────────────────
    async def upsert_event(self, event: Any, ikey: str, facts: dict) -> int:
        """INSERT event，若 idempotency_key 已存在則回傳既有 id（ADR-11）"""
        event_uid = str(uuid.uuid4())
        try:
            result = await self._s.execute(
                text("""
                    INSERT INTO notify_event (
                        event_uid, idempotency_key, event_type, severity, source,
                        occurred_at, payload, routing_facts, routed_status
                    ) VALUES (
                        :event_uid, :idempotency_key, :event_type, :severity, :source,
                        :occurred_at, :payload, :routing_facts, 'pending'
                    )
                    ON CONFLICT (event_uid) DO NOTHING
                    RETURNING id
                """),
                {
                    "event_uid":       event_uid,
                    "idempotency_key": ikey,
                    "event_type":      event.event_type,
                    "severity":        event.severity,
                    "source":          event.source,
                    "occurred_at":     event.occurred_at,  # TIMESTAMPTZ：需原生 datetime
                    "payload":         json.dumps(event.payload),  # JSONB：需先序列化為字串
                    "routing_facts":   json.dumps(facts),
                }
            )
            await self._s.flush()
            row = result.scalar()
            if row:
                return row
        except Exception:
            pass

        # 已存在：取出 id
        result = await self._s.execute(
            text("SELECT id FROM notify_event WHERE idempotency_key = :key LIMIT 1"),
            {"key": ikey}
        )
        return result.scalar()

    async def get_event(self, event_id: int) -> dict | None:
        result = await self._s.execute(
            text("SELECT * FROM notify_event WHERE id = :id"),
            {"id": event_id}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def mark_event_routed(self, event_id: int, status: str) -> None:
        await self._s.execute(
            text("UPDATE notify_event SET routed_status = :s WHERE id = :id"),
            {"s": status, "id": event_id}
        )

    # ────────────────────────────────────────────────────────
    # 訊息 (Outbox)
    # ────────────────────────────────────────────────────────
    async def message_exists(self, idempotency_key: str, endpoint_id: int) -> bool:
        result = await self._s.execute(
            text("""
                SELECT 1 FROM notify_message
                WHERE idempotency_key = :ikey AND endpoint_id = :eid LIMIT 1
            """),
            {"ikey": idempotency_key, "eid": endpoint_id}
        )
        return result.scalar() is not None

    async def create_message(self, data: dict) -> int:
        result = await self._s.execute(
            text("""
                INSERT INTO notify_message (
                    message_code, event_id, endpoint_id, channel_code,
                    idempotency_key, priority, status, subject, body, scheduled_at
                ) VALUES (
                    :message_code, :event_id, :endpoint_id, :channel_code,
                    :idempotency_key, :priority, :status, :subject, :body, :scheduled_at
                )
                ON CONFLICT (idempotency_key, endpoint_id) DO NOTHING
                RETURNING id
            """),
            data
        )
        await self._s.flush()
        return result.scalar()

    async def claim_batch(self, worker_id: str, batch_size: int) -> list[dict]:
        """FOR UPDATE SKIP LOCKED 原子取件（AC-32，§4.7）"""
        claimed_at = datetime.now(timezone.utc)  # TIMESTAMPTZ：需原生 datetime
        result = await self._s.execute(
            text("""
                UPDATE notify_message
                SET status = 'sending', claimed_at = :claimed_at, claimed_by = :worker_id
                WHERE id IN (
                    SELECT id FROM notify_message
                    WHERE status IN ('pending','failed')
                      AND scheduled_at <= NOW()
                    ORDER BY priority ASC, scheduled_at ASC
                    LIMIT :batch_size
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING *
            """),
            {"claimed_at": claimed_at, "worker_id": worker_id, "batch_size": batch_size}
        )
        return [dict(r) for r in result.mappings()]

    async def mark_sent(self, msg_id: int, provider_msg_id: str = "") -> None:
        await self._s.execute(
            text("""
                UPDATE notify_message
                SET status = 'sent', sent_at = NOW(), updated_at = NOW(),
                    attempt_count = attempt_count + 1
                WHERE id = :id
            """),
            {"id": msg_id}
        )

    async def mark_dead(self, msg_id: int, reason: str, failure_kind: str = "") -> None:
        await self._s.execute(
            text("""
                UPDATE notify_message
                SET status = 'dead', last_failure_kind = :fk, updated_at = NOW(),
                    attempt_count = attempt_count + 1
                WHERE id = :id
            """),
            {"id": msg_id, "fk": failure_kind[:32] if failure_kind else ""}
        )

    async def mark_failed_retry(self, msg_id: int, attempt: int, retry_at: datetime, fk: str) -> None:
        await self._s.execute(
            text("""
                UPDATE notify_message
                SET status = 'failed', attempt_count = :attempt,
                    next_retry_at = :retry_at, scheduled_at = :retry_at,
                    last_failure_kind = :fk, claimed_at = NULL, claimed_by = NULL,
                    updated_at = NOW()
                WHERE id = :id
            """),
            {"id": msg_id, "attempt": attempt, "retry_at": retry_at, "fk": fk[:32]}  # TIMESTAMPTZ：需原生 datetime
        )

    async def requeue_message(self, msg_id: int) -> None:
        """熔斷期間重排（保持 pending 狀態）"""
        await self._s.execute(
            text("UPDATE notify_message SET status = 'pending', claimed_at = NULL, claimed_by = NULL WHERE id = :id"),
            {"id": msg_id}
        )

    async def recover_stuck_messages(self, cutoff: datetime) -> int:
        result = await self._s.execute(
            text("""
                UPDATE notify_message
                SET status = 'pending', claimed_at = NULL, claimed_by = NULL, updated_at = NOW()
                WHERE status = 'sending' AND claimed_at < :cutoff
                RETURNING id
            """),
            {"cutoff": cutoff}  # TIMESTAMPTZ：需原生 datetime
        )
        rows = result.fetchall()
        return len(rows)

    async def query_messages(self, filters: dict) -> list[dict]:
        """多條件查詢（發送紀錄頁面，§9.2）"""
        conditions = ["1=1"]
        params     = {}
        if filters.get("status"):
            conditions.append("status = :status")
            params["status"] = filters["status"]
        if filters.get("channel_code"):
            conditions.append("channel_code = :channel_code")
            params["channel_code"] = filters["channel_code"]
        if filters.get("date_from"):
            conditions.append("created_at >= :date_from")
            params["date_from"] = filters["date_from"]
        if filters.get("date_to"):
            conditions.append("created_at <= :date_to")
            params["date_to"] = filters["date_to"]
        where = " AND ".join(conditions)
        limit  = min(int(filters.get("limit", 50)), 200)
        offset = int(filters.get("offset", 0))
        result = await self._s.execute(
            text(f"SELECT * FROM notify_message WHERE {where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
            {**params, "limit": limit, "offset": offset}
        )
        return [dict(r) for r in result.mappings()]

    async def list_digest_eligible_endpoints(self) -> list[dict]:
        """摘要排程候選端點：目前有 digest_pending 或 throttled 訊息在等待的端點（§8.3）"""
        result = await self._s.execute(text("""
            SELECT DISTINCT e.* FROM notify_endpoint e
            JOIN notify_message m ON m.endpoint_id = e.id
            WHERE m.status IN ('digest_pending', 'throttled')
              AND e.status = 'active' AND e.verify_status = 'verified'
        """))
        return [dict(r) for r in result.mappings()]

    async def list_pending_digest_messages(self, endpoint_id: int) -> list[dict]:
        result = await self._s.execute(
            text("""
                SELECT m.*, ev.payload AS event_payload, ev.event_type AS source_event_type
                FROM notify_message m
                JOIN notify_event ev ON ev.id = m.event_id
                WHERE m.endpoint_id = :eid AND m.status IN ('digest_pending', 'throttled')
                ORDER BY m.created_at
            """),
            {"eid": endpoint_id}
        )
        return [dict(r) for r in result.mappings()]

    async def mark_messages_digested(self, message_ids: list[int], digest_message_id: int | None) -> None:
        if not message_ids:
            return
        await self._s.execute(
            text("""
                UPDATE notify_message
                SET status = 'digested', digest_message_id = :dmid, updated_at = NOW()
                WHERE id = ANY(:ids)
            """),
            {"dmid": digest_message_id, "ids": message_ids}
        )

    async def get_message_by_code(self, message_code: str) -> dict | None:
        result = await self._s.execute(
            text("SELECT * FROM notify_message WHERE message_code = :code"),
            {"code": message_code}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def resend_message(self, msg_id: int) -> None:
        """管理者手動重送（AC-14）：reset dead → pending"""
        await self._s.execute(
            text("""
                UPDATE notify_message
                SET status = 'pending', scheduled_at = NOW(), claimed_at = NULL,
                    claimed_by = NULL, attempt_count = 0, next_retry_at = NULL,
                    updated_at = NOW()
                WHERE id = :id AND status = 'dead'
            """),
            {"id": msg_id}
        )

    # ────────────────────────────────────────────────────────
    # 投遞紀錄
    # ────────────────────────────────────────────────────────
    async def log_attempt(self, msg_id: int, data: dict) -> None:
        await self._s.execute(
            text("""
                INSERT INTO notify_delivery_log (
                    message_id, attempt_no, result, failure_kind,
                    failure_reason, provider_message_id, latency_ms
                ) VALUES (
                    :msg_id, :attempt_no, :result, :failure_kind,
                    :failure_reason, :provider_message_id, :latency_ms
                )
            """),
            {
                "msg_id":             msg_id,
                "attempt_no":         data.get("attempt_no", 1),
                "result":             data.get("result", "success"),
                "failure_kind":       data.get("failure_kind"),
                "failure_reason":     data.get("failure_reason"),
                "provider_message_id": data.get("provider_message_id"),
                "latency_ms":         data.get("latency_ms"),
            }
        )

    async def get_delivery_logs(self, msg_id: int) -> list[dict]:
        result = await self._s.execute(
            text("SELECT * FROM notify_delivery_log WHERE message_id = :mid ORDER BY attempt_no"),
            {"mid": msg_id}
        )
        return [dict(r) for r in result.mappings()]

    # ────────────────────────────────────────────────────────
    # 模板
    # ────────────────────────────────────────────────────────
    async def get_template(self, event_type: str, channel_code: str) -> dict | None:
        result = await self._s.execute(
            text("""
                SELECT * FROM notify_template
                WHERE event_type = :et AND channel_code = :cc
                LIMIT 1
            """),
            {"et": event_type, "cc": channel_code}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def list_templates(self) -> list[dict]:
        result = await self._s.execute(text("SELECT * FROM notify_template ORDER BY event_type, channel_code"))
        return [dict(r) for r in result.mappings()]

    async def upsert_template(self, data: dict) -> None:
        await self._s.execute(
            text("""
                INSERT INTO notify_template (template_code, event_type, channel_code, title_format, body_format, body_kind)
                VALUES (:template_code, :event_type, :channel_code, :title_format, :body_format, :body_kind)
                ON CONFLICT (event_type, channel_code) DO UPDATE
                SET title_format = EXCLUDED.title_format,
                    body_format  = EXCLUDED.body_format,
                    body_kind    = EXCLUDED.body_kind,
                    updated_at   = NOW()
            """),
            data
        )

    async def seed_template(self, data: dict) -> bool:
        """ON CONFLICT DO NOTHING（不覆蓋管理者已編輯的內容，§11.2 步驟 3）"""
        result = await self._s.execute(
            text("""
                INSERT INTO notify_template (template_code, event_type, channel_code, body_format, body_kind, is_default)
                VALUES (:template_code, :event_type, :channel_code, :body_format, :body_kind, :is_default)
                ON CONFLICT (template_code) DO NOTHING
                RETURNING id
            """),
            data
        )
        await self._s.flush()
        return result.scalar() is not None

    # ────────────────────────────────────────────────────────
    # 綁定 Token
    # ────────────────────────────────────────────────────────
    async def create_binding_token(self, data: dict) -> None:
        await self._s.execute(
            text("""
                INSERT INTO notify_binding_token (token_digest, purpose, channel_code, endpoint_id, recipient_id, expires_at)
                VALUES (:token_digest, :purpose, :channel_code, :endpoint_id, :recipient_id, :expires_at)
            """),
            data
        )

    async def get_binding_token(self, token_digest: str) -> dict | None:
        result = await self._s.execute(
            text("SELECT * FROM notify_binding_token WHERE token_digest = :d AND used_at IS NULL"),
            {"d": token_digest}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def consume_binding_token(self, token_digest: str) -> None:
        await self._s.execute(
            text("UPDATE notify_binding_token SET used_at = NOW() WHERE token_digest = :d"),
            {"d": token_digest}
        )

    # ────────────────────────────────────────────────────────
    # 自助連結 Token
    # ────────────────────────────────────────────────────────
    async def get_active_self_service_token(self, recipient_id: int) -> str | None:
        result = await self._s.execute(
            text("""
                SELECT token_digest FROM notify_self_service_token
                WHERE recipient_id = :rid AND status = 'active' LIMIT 1
            """),
            {"rid": recipient_id}
        )
        return result.scalar()

    async def get_self_service_token_by_digest(self, token_digest: str) -> dict | None:
        """§7.2 token 交換入口：只用雜湊摘要查詢，資料庫從不保存可直接使用的明文（FR-SS-14）"""
        result = await self._s.execute(
            text("SELECT * FROM notify_self_service_token WHERE token_digest = :d"),
            {"d": token_digest}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def create_self_service_token(self, data: dict) -> None:
        # 先 revoke 舊的（唯一索引保護）
        await self._s.execute(
            text("UPDATE notify_self_service_token SET status = 'revoked', revoked_at = NOW() WHERE recipient_id = :rid AND status = 'active'"),
            {"rid": data["recipient_id"]}
        )
        await self._s.execute(
            text("""
                INSERT INTO notify_self_service_token (token_digest, recipient_id, status)
                VALUES (:token_digest, :recipient_id, 'active')
            """),
            data
        )

    async def revoke_self_service_token(self, recipient_id: int) -> None:
        await self._s.execute(
            text("UPDATE notify_self_service_token SET status = 'revoked', revoked_at = NOW() WHERE recipient_id = :rid AND status = 'active'"),
            {"rid": recipient_id}
        )

    async def mark_self_service_token_used(self, token_digest: str) -> None:
        await self._s.execute(
            text("UPDATE notify_self_service_token SET last_used_at = NOW() WHERE token_digest = :d"),
            {"d": token_digest}
        )

    # ────────────────────────────────────────────────────────
    # 收件人偏好（M13，FR-SS-04/05/08）
    # ────────────────────────────────────────────────────────
    async def get_preference(self, recipient_id: int) -> dict | None:
        result = await self._s.execute(
            text("SELECT * FROM notify_recipient_preference WHERE recipient_id = :rid"),
            {"rid": recipient_id}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def upsert_preference(self, recipient_id: int, data: dict) -> None:
        # notify_recipient_preference 的 allowed_*/ceiling_*/watch_symbols 全部是 JSONB 欄位，
        # 用 text() 直接綁 dict/list 給 asyncpg 會炸掉，這裡的動態欄位一律先序列化為 JSON 字串。
        serialized = {k: json.dumps(v) for k, v in data.items()}
        payload = {**serialized, "recipient_id": recipient_id}
        cols = ", ".join(k for k in payload if k != "recipient_id")
        await self._s.execute(
            text(f"""
                INSERT INTO notify_recipient_preference (recipient_id, {cols})
                VALUES (:recipient_id, {", ".join(f":{k}" for k in payload if k != "recipient_id")})
                ON CONFLICT (recipient_id) DO UPDATE SET
                    {", ".join(f"{k} = EXCLUDED.{k}" for k in payload if k != "recipient_id")},
                    updated_at = NOW()
            """),
            payload
        )

    async def create_preference_audit(self, recipient_id: int, actor: str, change_summary: dict) -> None:
        await self._s.execute(
            text("""
                INSERT INTO notify_preference_audit (recipient_id, actor, change_summary)
                VALUES (:rid, :actor, :summary)
            """),
            {"rid": recipient_id, "actor": actor, "summary": json.dumps(change_summary)}  # JSONB
        )

    async def list_preference_audit(self, recipient_id: int, limit: int = 20) -> list[dict]:
        result = await self._s.execute(
            text("""
                SELECT * FROM notify_preference_audit
                WHERE recipient_id = :rid ORDER BY changed_at DESC LIMIT :limit
            """),
            {"rid": recipient_id, "limit": limit}
        )
        return [dict(r) for r in result.mappings()]

    # ────────────────────────────────────────────────────────
    # 每日用量計數（FR-PL-02、NFR-21，§4.5 閘門 2、§4.8 備援判斷）
    # ────────────────────────────────────────────────────────
    async def increment_quota(self, scope: str, scope_key: str, usage_date: date) -> int:
        """回傳遞增後的 used_count（原子 UPSERT）"""
        result = await self._s.execute(
            text("""
                INSERT INTO notify_quota_usage (scope, scope_key, usage_date, used_count)
                VALUES (:scope, :scope_key, :usage_date, 1)
                ON CONFLICT (scope, scope_key, usage_date)
                DO UPDATE SET used_count = notify_quota_usage.used_count + 1
                RETURNING used_count
            """),
            {"scope": scope, "scope_key": scope_key, "usage_date": usage_date}
        )
        return result.scalar()

    async def get_quota_usage(self, scope: str, scope_key: str, usage_date: date) -> int:
        result = await self._s.execute(
            text("""
                SELECT used_count FROM notify_quota_usage
                WHERE scope = :scope AND scope_key = :scope_key AND usage_date = :usage_date
            """),
            {"scope": scope, "scope_key": scope_key, "usage_date": usage_date}
        )
        return result.scalar() or 0

    # ────────────────────────────────────────────────────────
    # 告警防遞迴（RK-11，§4.10）
    # ────────────────────────────────────────────────────────
    async def check_and_bump_suppression(self, cooldown_key: str, cooldown_seconds: int) -> bool:
        """
        回傳 True 代表「應該發出這次告警」（不在冷卻期內或首次見到）；
        False 代表冷卻期內，僅累計次數、不重複發告警。
        """
        result = await self._s.execute(
            text("SELECT cooldown_until, occurrence_count FROM notify_suppression WHERE cooldown_key = :k"),
            {"k": cooldown_key}
        )
        row = result.mappings().first()
        now = datetime.now(timezone.utc)
        if row and row["cooldown_until"]:
            cooldown_until = row["cooldown_until"]
            if isinstance(cooldown_until, str):
                cooldown_until = datetime.fromisoformat(cooldown_until)
            if cooldown_until.tzinfo is None:
                cooldown_until = cooldown_until.replace(tzinfo=timezone.utc)
            if now < cooldown_until:
                await self._s.execute(
                    text("""
                        UPDATE notify_suppression
                        SET last_seen_at = NOW(), occurrence_count = occurrence_count + 1
                        WHERE cooldown_key = :k
                    """),
                    {"k": cooldown_key}
                )
                return False

        new_until = now + timedelta(seconds=cooldown_seconds)
        await self._s.execute(
            text("""
                INSERT INTO notify_suppression (cooldown_key, first_seen_at, last_seen_at, occurrence_count, cooldown_until)
                VALUES (:k, NOW(), NOW(), 1, :until)
                ON CONFLICT (cooldown_key) DO UPDATE SET
                    last_seen_at = NOW(), occurrence_count = 1, cooldown_until = EXCLUDED.cooldown_until
            """),
            {"k": cooldown_key, "until": new_until}  # TIMESTAMPTZ：需原生 datetime
        )
        return True

    # ────────────────────────────────────────────────────────
    # 自助頁「我收到的通知」（FR-SS-09）
    # ────────────────────────────────────────────────────────
    async def list_messages_for_recipient(self, recipient_id: int, days: int = 7, limit: int = 50) -> list[dict]:
        result = await self._s.execute(
            text("""
                SELECT m.* FROM notify_message m
                JOIN notify_endpoint e ON e.id = m.endpoint_id
                WHERE e.recipient_id = :rid
                  AND m.created_at >= NOW() - INTERVAL '1 day' * :days
                ORDER BY m.created_at DESC LIMIT :limit
            """),
            {"rid": recipient_id, "days": days, "limit": limit}
        )
        return [dict(r) for r in result.mappings()]

    # ────────────────────────────────────────────────────────
    # 統計（GET /stats，§11.4）
    # ────────────────────────────────────────────────────────
    async def stats(self) -> dict:
        result = await self._s.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending')                    AS pending,
                COUNT(*) FILTER (WHERE status = 'sending')                   AS sending,
                COUNT(*) FILTER (WHERE status = 'sent')                      AS sent,
                COUNT(*) FILTER (WHERE status = 'failed')                    AS failed,
                COUNT(*) FILTER (WHERE status = 'dead')                      AS dead,
                COUNT(*) FILTER (WHERE status = 'skipped_duplicate')         AS skipped_dup,
                COUNT(*) FILTER (WHERE status = 'deferred')                  AS deferred,
                COUNT(*) FILTER (WHERE status = 'digest_pending')            AS digest_pending,
                COUNT(*) FILTER (WHERE status = 'digested')                  AS digested,
                COUNT(*) FILTER (WHERE status = 'skipped_paused')            AS skipped_paused,
                EXTRACT(EPOCH FROM (NOW() - MIN(scheduled_at) FILTER (WHERE status = 'pending')))
                                                                               AS oldest_pending_age_sec
            FROM notify_message
            WHERE created_at >= NOW() - INTERVAL '24 hours'
        """))
        row = result.mappings().first()
        return dict(row) if row else {}

    # ────────────────────────────────────────────────────────
    # 稽核紀錄
    # ────────────────────────────────────────────────────────
    async def log_admin_action(self, actor: str, action: str, target: str, result: str, detail: dict = None) -> None:
        await self._s.execute(
            text("""
                INSERT INTO notify_admin_audit (actor, action, target, result, detail)
                VALUES (:actor, :action, :target, :result, :detail)
            """),
            {
                "actor": actor, "action": action, "target": target, "result": result,
                "detail": json.dumps(detail) if detail is not None else None,  # JSONB
            }
        )

    async def list_admin_audit(self, limit: int = 100) -> list[dict]:
        result = await self._s.execute(
            text("SELECT * FROM notify_admin_audit ORDER BY acted_at DESC LIMIT :limit"),
            {"limit": limit}
        )
        return [dict(r) for r in result.mappings()]

    async def stats_by_channel(self) -> list[dict]:
        result = await self._s.execute(text("""
            SELECT channel_code,
                   COUNT(*) FILTER (WHERE status = 'sent') AS sent,
                   COUNT(*) FILTER (WHERE status = 'dead') AS dead,
                   COUNT(*) AS total
            FROM notify_message
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY channel_code
        """))
        return [dict(r) for r in result.mappings()]

    async def failure_ranking(self, limit: int = 10) -> list[dict]:
        result = await self._s.execute(
            text("""
                SELECT failure_kind, COUNT(*) AS cnt
                FROM notify_delivery_log
                WHERE result != 'success' AND attempted_at >= NOW() - INTERVAL '7 days'
                GROUP BY failure_kind ORDER BY cnt DESC LIMIT :limit
            """),
            {"limit": limit}
        )
        return [dict(r) for r in result.mappings()]

    # ────────────────────────────────────────────────────────
    # 日誌清理
    # ────────────────────────────────────────────────────────
    async def purge_old_logs(self, retention_days: int) -> int:
        result = await self._s.execute(
            text("""
                DELETE FROM notify_delivery_log
                WHERE message_id IN (
                    SELECT id FROM notify_message
                    WHERE created_at < NOW() - INTERVAL '1 day' * :days
                    AND status IN ('sent','dead','digested','skipped_duplicate','skipped_paused')
                )
                RETURNING id
            """),
            {"days": retention_days}
        )
        return len(result.fetchall())
