import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch

import bcrypt

from starlette.requests import Request

from api.v1.endpoints import (
    cashflow,
    investment_notes,
    performance,
    portfolio,
    portfolio_settings,
    transactions,
    watchlist,
)
from core.owner_auth import (
    COOKIE_NAME,
    OwnerUnauthorizedException,
    create_owner_session_token,
    require_owner,
    set_owner_password,
    verify_owner_password,
    verify_owner_session_token,
)


def _request(cookie: str | None = None) -> Request:
    headers = []
    if cookie:
        headers.append((b"cookie", f"{COOKIE_NAME}={cookie}".encode()))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


class OwnerAuthTest(unittest.TestCase):
    def test_owner_session_cookie_is_accepted(self):
        actor = asyncio.run(require_owner(_request(create_owner_session_token())))
        self.assertEqual(actor, "owner")

    def test_missing_owner_session_is_rejected(self):
        with self.assertRaises(OwnerUnauthorizedException):
            asyncio.run(require_owner(_request()))

    def test_invalid_owner_session_is_rejected(self):
        with self.assertRaises(OwnerUnauthorizedException):
            asyncio.run(require_owner(_request("invalid-token")))

    def test_password_change_invalidates_old_password_and_session(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = os.path.join(temp_dir, ".env")
            old_hash = bcrypt.hashpw(b"old-password", bcrypt.gensalt()).decode()
            with open(env_path, "w", encoding="utf-8") as env_file:
                env_file.write(f"OWNER_PASSWORD_HASH={old_hash}\nNOTIFY_SECRET_KEY=test-secret\n")

            with patch("core.owner_auth.ENV_PATH", env_path):
                old_token = create_owner_session_token()
                set_owner_password("new-password")

                self.assertFalse(verify_owner_password("old-password"))
                self.assertTrue(verify_owner_password("new-password"))
                self.assertFalse(verify_owner_session_token(old_token))
                self.assertTrue(verify_owner_session_token(create_owner_session_token()))

    def test_all_portfolio_routers_require_owner(self):
        routers = [
            transactions.router,
            portfolio.router,
            performance.router,
            cashflow.dividend_router,
            cashflow.cashflow_router,
            watchlist.router,
            portfolio_settings.router,
            investment_notes.router,
        ]

        missing = [
            router.prefix
            for router in routers
            if not any(dependency.dependency is require_owner for dependency in router.dependencies)
        ]

        self.assertEqual(missing, [])