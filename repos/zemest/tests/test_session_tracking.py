"""Session + geo tracking (audit F19): user_sessions / site_users are now
populated on every login, keeping the admin analytics screens honest.
"""
from __future__ import annotations

import uuid

import pytest

from app.models.admin import SiteUser, UserSession
from app.utils.security import hash_password


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, host="127.0.0.1", headers=None):
        self.client = _FakeClient(host)
        self.headers = headers or {}
        self.headers.setdefault("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64) Chrome/125.0")


@pytest.mark.asyncio
class TestSessionTracking:
    async def test_record_user_session_writes_rows(self, db_session, test_user):
        from app.services.session_tracking import record_user_session

        await record_user_session(db_session, test_user, _FakeRequest())
        await db_session.commit()

        sessions = (await db_session.execute(
            UserSession.__table__.select()
        )).mappings().all()
        assert len(sessions) == 1
        s = sessions[0]
        assert s["user_id"] == test_user.id
        assert s["ip_address"]
        assert s["device_type"] == "desktop"
        assert s["browser"] == "Chrome"
        assert s["is_active"] is True

        site = (await db_session.execute(
            SiteUser.__table__.select()
        )).mappings().first()
        assert site is not None
        assert site["user_id"] == test_user.id
        assert site["last_ip"]
        assert site["last_seen"] is not None

    async def test_upsert_does_not_duplicate_site_user(self, db_session, test_user):
        from app.services.session_tracking import record_user_session

        await record_user_session(db_session, test_user, _FakeRequest())
        await record_user_session(db_session, test_user, _FakeRequest())
        await db_session.commit()

        site_rows = (await db_session.execute(
            SiteUser.__table__.select()
        )).mappings().all()
        assert len(site_rows) == 1
        session_rows = (await db_session.execute(
            UserSession.__table__.select()
        )).mappings().all()
        assert len(session_rows) == 2  # two logins -> two session rows

    async def test_login_route_creates_session(self, client, db_session):
        from app.models.user import User

        user = User(
            id=uuid.uuid4(),
            name="Login Flow",
            email=f"loginflow-{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=hash_password("passw0rd123"),
        )
        db_session.add(user)
        await db_session.commit()

        resp = await client.post("/api/auth/login", json={
            "email": user.email,
            "password": "passw0rd123",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

        # The session row was written by the same transaction.
        await db_session.commit()
        sessions = (await db_session.execute(
            UserSession.__table__.select().where(UserSession.user_id == user.id)
        )).mappings().all()
        assert len(sessions) == 1

    async def test_failed_login_writes_nothing(self, client, db_session):
        resp = await client.post("/api/auth/login", json={
            "email": "ghost@example.com",
            "password": "wrongpass",
        })
        assert resp.status_code == 401
        await db_session.commit()
        sessions = (await db_session.execute(
            UserSession.__table__.select()
        )).mappings().all()
        assert sessions == []

    async def test_mark_sessions_inactive(self, db_session, test_user):
        from app.services.session_tracking import (
            mark_sessions_inactive, record_user_session,
        )

        await record_user_session(db_session, test_user, _FakeRequest())
        await db_session.commit()
        await mark_sessions_inactive(db_session, test_user.id)
        await db_session.commit()

        sessions = (await db_session.execute(
            UserSession.__table__.select()
        )).mappings().all()
        assert sessions[0]["is_active"] in (False, 0)

    async def test_admin_analytics_overview_counts_sessions(
        self, client, db_session, test_user
    ):
        """F19 regression: the admin overview no longer reports zero."""
        from app.services.session_tracking import record_user_session
        from app.utils.security import create_access_token

        test_user.is_superadmin = True
        db_session.add(test_user)
        await record_user_session(db_session, test_user, _FakeRequest())
        await db_session.commit()

        headers = {"Authorization": f"Bearer {create_access_token({'sub': str(test_user.id)})}"}
        resp = await client.get("/api/admin/analytics/overview", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["active_sessions"] >= 1

    async def test_geo_distribution_populated_when_geo_resolved(
        self, db_session, test_user, monkeypatch
    ):
        """Geo fields flow through when GeoLite2 resolves the IP."""
        from app.services.session_tracking import record_user_session

        monkeypatch.setattr(
            "app.services.session_tracking.locate_ip",
            lambda ip: {
                "country": "Egypt", "country_code": "EG",
                "city": "Cairo", "lat": 30.04, "lon": 31.23,
            },
        )
        await record_user_session(db_session, test_user, _FakeRequest())
        await db_session.commit()

        session = (await db_session.execute(
            UserSession.__table__.select()
        )).mappings().first()
        assert session["country"] == "Egypt"
        assert session["city"] == "Cairo"

        site = (await db_session.execute(
            SiteUser.__table__.select()
        )).mappings().first()
        assert site["last_country"] == "Egypt"
        assert site["last_city"] == "Cairo"
        assert site["last_latitude"] == 30.04
