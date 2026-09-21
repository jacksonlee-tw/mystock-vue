import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from ai.errors import AIDisabledException, AIQuotaExceededException
from core.owner_auth import require_owner
from main import app

PROPOSAL = {"note_id": 7, "suggested_subject": "主旨", "topic_tags": [], "symbols": [], "transcriptions": []}


class NoteAiEndpointTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[require_owner] = lambda: None
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

    def test_requires_owner_auth(self):
        app.dependency_overrides.clear()
        # 沒有 cookie／Bearer token 一律 401，兩支端點都是
        self.assertEqual(self.client.get("/api/v1/note-ai/status").status_code, 401)
        self.assertEqual(self.client.post("/api/v1/note-ai/notes/7/analyze", json={}).status_code, 401)

    def test_status_reports_enabled_only_when_both_switches_are_on(self):
        cases = [(True, True, True), (True, False, False), (False, True, False)]
        for master, note_flag, expected in cases:
            with self.subTest(master=master, note_flag=note_flag), \
                    patch("api.v1.endpoints.note_ai.ai_config.is_enabled", return_value=master), \
                    patch("api.v1.endpoints.note_ai.ai_config.get_note_ai_enabled", return_value=note_flag), \
                    patch("note_ai.analyzer._daily_call_count", AsyncMock(return_value=3)):
                data = self.client.get("/api/v1/note-ai/status").json()["data"]
                self.assertEqual(data["enabled"], expected)
                self.assertEqual(data["used_today"], 3)
                self.assertIn("default_model", data)

    def test_status_survives_database_outage(self):
        with patch("note_ai.analyzer._daily_call_count", AsyncMock(side_effect=ConnectionError("db down"))):
            res = self.client.get("/api/v1/note-ai/status")
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.json()["data"]["used_today"])

    def test_analyze_unknown_note_is_404(self):
        with patch("api.v1.endpoints.note_ai.investment_note_service.get_note", AsyncMock(return_value=None)):
            res = self.client.post("/api/v1/note-ai/notes/999/analyze", json={})
        self.assertEqual(res.status_code, 404)

    def test_analyze_returns_proposal_with_disclaimer_and_passes_provider_and_model(self):
        analyze = AsyncMock(return_value=PROPOSAL)
        with patch("api.v1.endpoints.note_ai.investment_note_service.get_note", AsyncMock(return_value={"id": 7})), \
                patch("api.v1.endpoints.note_ai.analyzer.analyze_note", analyze):
            res = self.client.post("/api/v1/note-ai/notes/7/analyze", json={"provider": "gemini", "model": "gemini-2.5-flash"})
        body = res.json()
        self.assertEqual((res.status_code, body["success"], body["data"]), (200, True, PROPOSAL))
        self.assertIn("不構成投資建議", body["disclaimer"])
        self.assertEqual(analyze.await_args.kwargs, {"provider_code": "gemini", "model": "gemini-2.5-flash"})

    def test_disabled_maps_to_403_through_the_existing_global_handler(self):
        with patch("api.v1.endpoints.note_ai.investment_note_service.get_note", AsyncMock(return_value={"id": 7})), \
                patch("api.v1.endpoints.note_ai.analyzer.analyze_note", AsyncMock(side_effect=AIDisabledException("off"))):
            res = self.client.post("/api/v1/note-ai/notes/7/analyze", json={})
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["error"]["code"], "AI_DISABLED")

    def test_quota_maps_to_429(self):
        with patch("api.v1.endpoints.note_ai.investment_note_service.get_note", AsyncMock(return_value={"id": 7})), \
                patch("api.v1.endpoints.note_ai.analyzer.analyze_note", AsyncMock(side_effect=AIQuotaExceededException("full"))):
            res = self.client.post("/api/v1/note-ai/notes/7/analyze", json={})
        self.assertEqual(res.status_code, 429)


if __name__ == "__main__":
    unittest.main()
