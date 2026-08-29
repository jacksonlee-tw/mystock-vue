from __future__ import annotations

import os
import secrets

from dotenv import load_dotenv, set_key
from fastapi import Request
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
COOKIE_NAME = "mystock_owner"
DEFAULT_OWNER_PASSWORD_HASH = "$2b$12$hHR6ipPYr4..H8CnkQ2eLecdtdJWQ8VRwJAAiUIvECB1AUnrjlW/6"


def _env(key: str, default: str = "") -> str:
    load_dotenv(ENV_PATH, override=True)
    return os.getenv(key, default).strip()


def get_owner_password_hash() -> str:
    return _env("OWNER_PASSWORD_HASH", "") or DEFAULT_OWNER_PASSWORD_HASH


def set_owner_password(plain: str) -> None:
    import bcrypt

    password_hash = bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
    set_key(ENV_PATH, "OWNER_PASSWORD_HASH", password_hash, quote_mode="never")


def get_owner_api_token() -> str:
    return _env("OWNER_API_TOKEN", "")


def get_owner_session_ttl_hours() -> int:
    try:
        return int(_env("OWNER_SESSION_TTL_HOURS", "12"))
    except ValueError:
        return 12


def _owner_signer() -> TimestampSigner:
    secret = ":".join([
        _env("NOTIFY_SECRET_KEY", "fallback-dev-secret-change-me"),
        get_owner_password_hash(),
        "owner",
    ])
    return TimestampSigner(secret, salt="owner-session")


def create_owner_session_token() -> str:
    return _owner_signer().sign("owner").decode()


def verify_owner_session_token(token: str) -> bool:
    try:
        _owner_signer().unsign(token, max_age=get_owner_session_ttl_hours() * 3600)
        return True
    except (SignatureExpired, BadSignature):
        return False


def verify_owner_password(plain: str) -> bool:
    try:
        import bcrypt
    except ImportError:
        return False

    stored_hash = get_owner_password_hash()
    if not stored_hash:
        return False
    try:
        return bcrypt.checkpw(plain.encode(), stored_hash.encode())
    except Exception:
        return False


class OwnerUnauthorizedException(Exception):
    pass


async def require_owner(request: Request) -> str:
    cookie = request.cookies.get(COOKIE_NAME, "")
    if cookie and verify_owner_session_token(cookie):
        return "owner"

    auth = request.headers.get("Authorization", "")
    token = get_owner_api_token()
    if token and auth.startswith("Bearer ") and secrets.compare_digest(auth[7:], token):
        return "owner:api"

    raise OwnerUnauthorizedException("此功能需要擁有者授權")