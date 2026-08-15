"""
notify/templating.py
M10 模板引擎（§4.6，ADR-07）
- seed_templates()：啟動時把 .j2 種入 DB（ON CONFLICT DO NOTHING，不覆蓋管理者已編輯的內容）
- render()：三層回退 (event_type × channel → event_type × default_channel → __default__)
- preview()：管理介面用，不落地
使用 Jinja2 SandboxedEnvironment（ADR-07），禁止任意程式碼執行
"""
from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Any

from jinja2.sandbox import SandboxedEnvironment
from jinja2 import TemplateNotFound, UndefinedError

logger = logging.getLogger("mystock-backend")

TEMPLATES_DIR = Path(__file__).parent / "templates"
DISCLAIMER    = "本訊息為系統依既定規則產生的資訊提示，非投資建議。投資有風險，請審慎評估。"

# Jinja2 沙箱環境（ADR-07）
_jinja_env = SandboxedEnvironment(
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=False,
)


# ── 訊號標籤對照 ──────────────────────────────────────────────
_SIGNAL_META: dict[str, dict] = {
    "BUY":     {"emoji": "📈", "signal_label": "買進訊號"},
    "SELL":    {"emoji": "📉", "signal_label": "賣出訊號"},
    "WARNING": {"emoji": "⚠️", "signal_label": "警示訊號"},
}
_STRENGTH_LABELS: dict[str, str] = {
    "strong":   "強",
    "moderate": "中",
    "weak":     "弱",
}


def _enrich_context(event_type: str, payload: dict, extra: dict) -> dict:
    """在模板變數中加入 composer 統一附加的欄位"""
    ctx = {**payload, **extra}
    ctx.setdefault("disclaimer", DISCLAIMER)
    ctx.setdefault("manage_url", None)
    ctx.setdefault("chart_url", "")

    if event_type == "ALERT_SIGNAL":
        signal_type     = payload.get("signal_type", "")
        signal_strength = payload.get("signal_strength", "")
        meta = _SIGNAL_META.get(signal_type, {"emoji": "🔔", "signal_label": signal_type})
        ctx.setdefault("emoji",          meta["emoji"])
        ctx.setdefault("signal_label",   meta["signal_label"])
        ctx.setdefault("strength_label", _STRENGTH_LABELS.get(signal_strength, signal_strength))
        ctx.setdefault("filters_passed", payload.get("filters_passed", []))

    return ctx


# ── render：三層回退 ──────────────────────────────────────────
async def render(
    event_type:   str,
    channel_code: str,
    payload:      dict,
    extra_ctx:    dict,
    repo:         Any,
) -> tuple[str | None, str]:
    """
    回傳 (subject, body)。
    三層回退（§4.6，R5）：
    1. DB 模板 (event_type × channel_code)
    2. 本地 .j2 檔案 (event_type × channel_code)
    3. __default__ 回退模板
    """
    ctx = _enrich_context(event_type, payload, extra_ctx)

    # 1. DB 模板
    tmpl_row = await repo.get_template(event_type, channel_code)
    if tmpl_row and tmpl_row.get("body_format"):
        try:
            subject = _render_str(tmpl_row.get("title_format"), ctx)
            body    = _render_str(tmpl_row["body_format"], ctx)
            return subject, body
        except Exception as exc:
            logger.warning("[通知] DB 模板渲染失敗 (%s×%s): %s", event_type, channel_code, exc)

    # 2. 本地 .j2 檔案
    j2_path = TEMPLATES_DIR / f"{event_type.lower()}.{channel_code}.j2"
    if j2_path.exists():
        try:
            body = _render_file(j2_path, ctx)
            return None, body
        except Exception as exc:
            logger.warning("[通知] 本地模板渲染失敗 (%s): %s", j2_path.name, exc)

    # 3. __default__ 回退
    ctx_with_meta = {
        "event_type_label": event_type.replace("_", " ").title(),
        "title":            payload.get("stock_name", payload.get("market", "")),
        "occurred_at":      extra_ctx.get("occurred_at", ""),
        **ctx,
    }
    default_path = TEMPLATES_DIR / "__default__.txt.j2"
    if default_path.exists():
        try:
            body = _render_file(default_path, ctx_with_meta)
            return None, body
        except Exception as exc:
            logger.error("[通知] 回退模板渲染失敗: %s", exc)

    # 最後防線：純文字
    body = f"[{event_type}] 系統通知\n{payload}"
    return None, body


def _render_str(template_str: str | None, ctx: dict) -> str | None:
    if not template_str:
        return None
    return _jinja_env.from_string(template_str).render(**ctx)


def _render_file(path: Path, ctx: dict) -> str:
    return _jinja_env.from_string(path.read_text(encoding="utf-8")).render(**ctx)


# ── preview：管理介面用 ────────────────────────────────────────
async def preview(
    event_type:    str,
    channel_code:  str,
    template_body: str,
    template_title: str | None,
    sample_payload: dict,
    endpoint_ctx:   dict,
    repo:          Any,
) -> dict:
    """POST /templates/preview：渲染預覽，不落地（UC-07）"""
    ctx = _enrich_context(event_type, sample_payload, endpoint_ctx)
    try:
        subject = _render_str(template_title, ctx)
        body    = _render_str(template_body, ctx)
        return {"ok": True, "subject": subject, "body": body}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


# ── seed_templates：啟動時種入 DB ─────────────────────────────
async def seed_templates(repo: Any) -> None:
    """
    讀取 templates/*.j2 並以 ON CONFLICT DO NOTHING 種入 notify_template（§11.2 步驟 3）。
    不覆蓋管理者已編輯的模板。
    """
    if not TEMPLATES_DIR.exists():
        return

    # notify_template.channel_code 有 FK 指向 notify_channel，__default__.txt.j2 的
    # "txt" 只是純檔案回退（render() 第 3 層直接讀檔，不查 DB），不對應真實管道，故略過種入
    valid_channels = {c["channel_code"] for c in await repo.list_channels()}

    seeded = 0
    for j2_file in TEMPLATES_DIR.glob("*.j2"):
        stem  = j2_file.stem  # e.g. "alert_signal.email" or "__default__.txt"
        parts = stem.split(".")
        if len(parts) < 2:
            continue

        if stem.startswith("__default__"):
            event_type   = "__default__"
            channel_code = parts[-1] if len(parts) > 1 else "email"
        else:
            channel_code = parts[-1]                 # email / telegram
            event_type   = "_".join(parts[:-1]).upper()  # alert_signal → ALERT_SIGNAL

        if channel_code not in valid_channels:
            continue

        body_format   = j2_file.read_text(encoding="utf-8")
        template_code = f"{event_type}__{channel_code}"

        try:
            inserted = await repo.seed_template({
                "template_code": template_code,
                "event_type":    event_type,
                "channel_code":  channel_code,
                "body_format":   body_format,
                "body_kind":     "html" if channel_code == "email" else "text",
                "is_default":    stem.startswith("__default__"),
            })
            if inserted:
                seeded += 1
        except Exception as exc:
            logger.warning("[通知] 模板種入失敗 (%s): %s", template_code, exc)

    logger.info("[通知] 模板種入完成：%d 個模板已建立", seeded)
