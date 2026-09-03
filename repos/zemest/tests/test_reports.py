"""Reports module tests — user files a report, admin triages it.

Covers the product requirements:
- dashboard "Report" section: user submits title + subject
- reports land in the admin panel with everything about the user
  (email, plan, signup IP, shops, sessions)
- status workflow open → in_review → resolved
- Telegram notification wiring (inert unless configured — verified via the
  fire-and-forget path, never blocking the request)
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from app.models.report import SupportReport
from app.models.user import User
from app.services import report_service
from app.services.telegram_notify import notify_admin_async, telegram_configured
from app.utils.security import create_access_token, hash_password


@pytest_asyncio.fixture
async def admin_headers(db_session):
    admin = User(
        id=uuid.uuid4(),
        name="Report Admin",
        email="report-admin@test.local",
        is_superadmin=True,
        hashed_password=hash_password("adminpass123"),
    )
    db_session.add(admin)
    await db_session.commit()
    return {"Authorization": f"Bearer {create_access_token({'sub': str(admin.id)})}"}


@pytest.mark.asyncio
class TestUserReports:
    async def test_create_and_list_own_reports(self, client, auth_headers):
        resp = await client.post(
            "/api/reports",
            json={
                "title": "WhatsApp channel disconnected",
                "subject": "My WhatsApp channel stopped replying yesterday at 8pm.",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text
        report = resp.json()
        assert report["status"] == "open"
        assert report["code"].startswith("ZM-")

        resp = await client.get("/api/reports", headers=auth_headers)
        assert resp.status_code == 200
        mine = resp.json()
        assert any(r["id"] == report["id"] for r in mine)

    async def test_validation_minimums(self, client, auth_headers):
        # Title required
        resp = await client.post(
            "/api/reports", json={"title": "", "subject": "x" * 20}, headers=auth_headers
        )
        assert resp.status_code in (400, 422)
        # Subject needs substance (min 10 chars)
        resp = await client.post(
            "/api/reports", json={"title": "T", "subject": "short"}, headers=auth_headers
        )
        assert resp.status_code in (400, 422)

    async def test_reports_require_auth(self, client):
        resp = await client.get("/api/reports")
        assert resp.status_code == 401
        resp = await client.post(
            "/api/reports", json={"title": "T", "subject": "x" * 20}
        )
        assert resp.status_code == 401

    async def test_users_only_see_own_reports(
        self, client, db_session, auth_headers, test_user
    ):
        """One user's report must never appear in another user's list."""
        other = User(
            id=uuid.uuid4(),
            name="Other",
            email="other-reports@test.local",
            hashed_password=hash_password("otherpass123"),
        )
        db_session.add(other)
        await db_session.commit()

        await report_service.create_report(
            db_session, test_user, "Mine", "This report belongs to the test user."
        )
        await db_session.commit()

        other_token = create_access_token({"sub": str(other.id)})
        resp = await client.get(
            "/api/reports", headers={"Authorization": f"Bearer {other_token}"}
        )
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
class TestAdminReports:
    async def _file_report(self, db_session, test_user):
        report = await report_service.create_report(
            db_session,
            test_user,
            "Agent speaks wrong dialect",
            "The agent replies in Gulf Arabic but our customers are in Cairo.",
        )
        await db_session.commit()
        return report

    async def test_admin_sees_all_reports_with_context(
        self, client, db_session, admin_headers, auth_headers, test_user, test_tenant
    ):
        report = await self._file_report(db_session, test_user)

        resp = await client.get("/api/admin/reports", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        match = [r for r in data["reports"] if r["id"] == str(report.id)]
        assert match
        entry = match[0]
        assert entry["user"]["email"] == test_user.email
        assert entry["user"]["shops"] >= 1  # test_tenant fixture shop
        assert entry["status"] == "open"

    async def test_non_admin_blocked(self, client, auth_headers):
        resp = await client.get("/api/admin/reports", headers=auth_headers)
        assert resp.status_code == 403

    async def test_report_detail_with_user_activity(
        self, client, db_session, admin_headers, test_user
    ):
        report = await self._file_report(db_session, test_user)
        resp = await client.get(f"/api/admin/reports/{report.id}", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Agent speaks wrong dialect"
        assert body["user"]["name"] == test_user.name
        assert "recent_sessions" in body["user"]

    async def test_status_workflow(
        self, client, db_session, admin_headers, auth_headers, test_user
    ):
        report = await self._file_report(db_session, test_user)

        resp = await client.patch(
            f"/api/admin/reports/{report.id}",
            json={"status": "in_review", "admin_note": "Looking into the dialect config."},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_review"

        resp = await client.patch(
            f"/api/admin/reports/{report.id}",
            json={"status": "resolved"},
            headers=admin_headers,
        )
        assert resp.status_code == 200

        # User sees the resolution
        resp = await client.get("/api/reports", headers=auth_headers)
        mine = resp.json()
        match = [r for r in mine if r["id"] == str(report.id)][0]
        assert match["status"] == "resolved"
        assert match["resolved_at"] is not None

    async def test_invalid_status_rejected(self, client, db_session, admin_headers, test_user):
        report = await self._file_report(db_session, test_user)
        resp = await client.patch(
            f"/api/admin/reports/{report.id}",
            json={"status": "deleted"},
            headers=admin_headers,
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
class TestTelegramWiring:
    async def test_notify_is_inert_without_config(self, db_session, test_user):
        """No env → no-op, and the report creation path is unaffected."""
        assert telegram_configured() is False
        # Must not raise or block
        notify_admin_async("should be a silent no-op")
        report = await report_service.create_report(
            db_session, test_user, "Telegram off", "Report created while Telegram is not configured."
        )
        await db_session.commit()
        assert report.id is not None

    async def test_notify_fires_when_configured(self, db_session, test_user, monkeypatch):
        sent: list[str] = []

        # report_service binds notify_admin_async in its own namespace —
        # patch it THERE so create_report picks up the spy.
        from app.services import report_service as _rs

        monkeypatch.setattr(_rs, "notify_admin_async", lambda t: sent.append(t))

        report = await _rs.create_report(
            db_session, test_user, "Telegram on", "Report created while Telegram IS configured."
        )
        await db_session.commit()
        assert any(report.code in s for s in sent), "admin alert must carry the report code"
