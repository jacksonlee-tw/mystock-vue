"""
notify/config.py
整合訊息通知平台設定讀取
遵循既有 config.py 慣例：load_dotenv(override=True)，改 .env 不需重啟（NFR-14，鐵則 R8）
"""
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")


def _env(key: str, default: str = "") -> str:
    load_dotenv(ENV_PATH, override=True)
    return os.getenv(key, default).strip()


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    return _env(key, str(default)).lower() in ("true", "1", "yes")


def _env_list(key: str, default: str) -> list[str]:
    raw = _env(key, default)
    return [v.strip() for v in raw.split(",") if v.strip()]


# ── 總開關 ─────────────────────────────────────────────────────
def is_enabled() -> bool:
    return _env_bool("NOTIFY_ENABLED", False)


def get_secret_key() -> str:
    """Fernet 金鑰（ADR-08）"""
    return _env("NOTIFY_SECRET_KEY", "")


def get_public_base_url() -> str:
    return _env("PUBLIC_BASE_URL", "http://localhost:5173")


# ── 管理端授權（§7.3）─────────────────────────────────────────
def get_owner_password_hash() -> str:
    return _env("OWNER_PASSWORD_HASH", "")


def get_owner_api_token() -> str:
    return _env("OWNER_API_TOKEN", "")


def get_owner_session_ttl_hours() -> int:
    return _env_int("OWNER_SESSION_TTL_HOURS", 12)


def get_owner_session_secret() -> str:
    """itsdangerous 簽章金鑰（從 NOTIFY_SECRET_KEY 衍生）"""
    return _env("NOTIFY_SECRET_KEY", "fallback-dev-secret-change-me") + ":owner"


def get_self_service_session_secret() -> str:
    return _env("NOTIFY_SECRET_KEY", "fallback-dev-secret-change-me") + ":self"


# ── 發送調度（鐵則 R8，所有數量限制可設定）──────────────────────
def get_poll_interval_sec() -> int:
    return _env_int("NOTIFY_POLL_INTERVAL_SEC", 10)


def get_batch_size() -> int:
    return _env_int("NOTIFY_BATCH_SIZE", 20)


def get_max_retry() -> int:
    return _env_int("NOTIFY_MAX_RETRY", 3)


def get_retry_backoff_sec() -> list[int]:
    raw = _env("NOTIFY_RETRY_BACKOFF_SEC", "60,300,1800")
    try:
        return [int(v.strip()) for v in raw.split(",") if v.strip()]
    except ValueError:
        return [60, 300, 1800]


def get_stuck_timeout_min() -> int:
    return _env_int("NOTIFY_STUCK_TIMEOUT_MIN", 10)


def get_circuit_threshold() -> int:
    return _env_int("NOTIFY_CIRCUIT_THRESHOLD", 5)


def get_circuit_cooldown_sec() -> int:
    return _env_int("NOTIFY_CIRCUIT_COOLDOWN_SEC", 300)


def get_circuit_cooldown_max_sec() -> int:
    return _env_int("NOTIFY_CIRCUIT_COOLDOWN_MAX_SEC", 3600)


# ── 通知政策預設值 ─────────────────────────────────────────────
def get_default_daily_limit() -> int:
    return _env_int("NOTIFY_DEFAULT_DAILY_LIMIT", 30)


def get_default_quiet_start() -> str:
    return _env("NOTIFY_DEFAULT_QUIET_START", "22:00")


def get_default_quiet_end() -> str:
    return _env("NOTIFY_DEFAULT_QUIET_END", "08:00")


def get_default_timezone() -> str:
    return _env("NOTIFY_DEFAULT_TIMEZONE", "Asia/Taipei")


def get_default_strengths() -> list[str]:
    return _env_list("NOTIFY_DEFAULT_STRENGTHS", "strong,moderate")


def get_digest_time_tw() -> str:
    return _env("NOTIFY_DIGEST_TIME_TW", "15:00")


def get_digest_time_us() -> str:
    return _env("NOTIFY_DIGEST_TIME_US", "07:00")


def get_log_retention_days() -> int:
    return _env_int("NOTIFY_LOG_RETENTION_DAYS", 90)


# ── Email 管道 ─────────────────────────────────────────────────
def get_email_daily_budget() -> int:
    return _env_int("NOTIFY_EMAIL_DAILY_BUDGET", 350)


def get_email_rate_per_min() -> int:
    return _env_int("NOTIFY_RATE_EMAIL_PER_MIN", 30)


def get_email_subject_prefix() -> str:
    return _env("NOTIFY_EMAIL_SUBJECT_PREFIX", "【MyStock】")


# ── Telegram 管道 ──────────────────────────────────────────────
def get_telegram_rate_per_min() -> int:
    return _env_int("NOTIFY_RATE_TELEGRAM_PER_MIN", 20)


def get_telegram_webhook_base() -> str:
    return _env("TELEGRAM_WEBHOOK_BASE", "")


def get_telegram_webhook_secret() -> str:
    return _env("TELEGRAM_WEBHOOK_SECRET", "")


# ── 開發輔助 ───────────────────────────────────────────────────
def is_dry_run() -> bool:
    return _env_bool("NOTIFY_DRY_RUN", False)


def allow_insecure_cookie() -> bool:
    return _env_bool("NOTIFY_ALLOW_INSECURE_COOKIE", False)
