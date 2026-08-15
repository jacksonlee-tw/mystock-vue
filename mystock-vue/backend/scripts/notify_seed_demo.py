"""建立整合訊息通知平台的示範收件人、群組、端點與訂閱規則（開發/展示用，非必要腳本）。

資料形狀對齊 docs/9.整合訊息系統_Telegram/prototype/shared.js 的 MOCK_RECIPIENTS/MOCK_SUBSCRIPTIONS，
讓管理介面一開就有東西可看，方便對照原型驗收畫面。可重複執行（以 code 判斷是否已存在，不會重複建立）。

用法：python scripts/notify_seed_demo.py
前提：backend/.env 已設定 NOTIFY_ENABLED=true、NOTIFY_SECRET_KEY，且 V3/V4 migration 已套用。
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.session import get_async_session, dispose_engine
from repositories.notify_repository import NotifyRepository
from notify import recipients as recipients_mod


async def _ensure_group(repo: NotifyRepository, name: str) -> dict:
    groups = await repo.list_groups_with_members()
    existing = next((g for g in groups if g["group_name"] == name), None)
    if existing:
        return existing
    return await recipients_mod.create_group(name, repo)


async def _ensure_recipient(repo: NotifyRepository, name: str, group_names: list[str]) -> dict:
    existing = next((r for r in await repo.list_recipients() if r["display_name"] == name), None)
    if existing:
        return existing
    return await recipients_mod.create_recipient(name, group_names, repo)


async def main() -> None:
    async with get_async_session() as session:
        repo = NotifyRepository(session)

        print("建立收件群組…")
        await _ensure_group(repo, "本人")
        await _ensure_group(repo, "家人")
        await _ensure_group(repo, "同好")

        print("建立收件人…")
        jackson  = await _ensure_recipient(repo, "Jackson（我）", ["本人"])
        family_a = await _ensure_recipient(repo, "家人 A", ["家人"])
        friend_b = await _ensure_recipient(repo, "同好 B", ["同好"])

        print("建立示範訂閱規則（若已存在同名規則則略過）…")
        existing_rules = {s["rule_name"] for s in await repo.list_all_subscriptions()}

        async def _rule(name, event_type, filters, target_key, target_val):
            if name in existing_rules:
                return
            payload = {
                "rule_code": f"sub-{name}",
                "rule_name": name,
                "event_type": event_type,
                "filter_conditions": filters,
                "target_group_id": None,
                "target_recipient_id": None,
                "target_endpoint_id": None,
                "status": "enabled",
                "priority": 100,
            }
            payload[target_key] = target_val
            await repo.create_subscription(payload)

        groups = {g["group_name"]: g["id"] for g in await repo.list_groups_with_members()}

        await _rule(
            "本人：全部訊號", "ALERT_SIGNAL",
            {"strengths": ["strong", "moderate"]},
            "target_group_id", groups["本人"],
        )
        await _rule(
            "家人：台股強訊號", "ALERT_SIGNAL",
            {"markets": ["tw"], "strengths": ["strong"]},
            "target_group_id", groups["家人"],
        )
        await _rule(
            "每日摘要", "ALERT_DIGEST",
            {},
            "target_group_id", groups["本人"],
        )
        await _rule(
            "系統異常告警", "SYSTEM_HEALTH",
            {},
            "target_recipient_id", jackson["id"],
        )

        await session.commit()
        print("完成。請至管理介面「收件人」頁為以上收件人新增 Email／Telegram 端點並完成驗證／綁定。")
        print(f"收件人代碼：{jackson['recipient_code']}, {family_a['recipient_code']}, {friend_b['recipient_code']}")

    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
