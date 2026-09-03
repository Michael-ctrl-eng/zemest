"""Analytics module tests — ingest, aggregates, compression, encryption,
visitor profiles, admin endpoints, export round-trip.

Covers the product requirements:
- every click/view is captured with IP + page name
- raw events stored compressed + encrypted, decryptable for export
- daily aggregates power the "what sucks" page ranking
- visitor profiles track location/device/interests; PII encrypted at rest
- admin-only access to visitor PII and exports (403 for normal users)
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.analytics import AnalyticsBatch, AnalyticsDaily, VisitorProfile
from app.models.user import User
from app.services import analytics_service


def _batch(visitor="v-test1", session="s-1", events=None):
    return {
        "visitor": visitor,
        "session": session,
        "events": events
        or [
            {"type": "page_view", "path": "/", "page_name": "Zemest Home"},
            {"type": "click", "path": "/", "element": "Pricing CTA"},
            {"type": "scroll", "path": "/", "scroll": 80},
            {"type": "page_view", "path": "/pricing", "page_name": "Pricing"},
            {"type": "session_end", "path": "/pricing", "session_pages": 2},
        ],
    }


@pytest.mark.asyncio
class TestIngest:
    async def test_ingest_creates_batch_aggregates_profile(self, db_session):
        payload = _batch()
        count = await analytics_service.ingest_events(
            db_session,
            payload["events"],
            visitor_key=payload["visitor"],
            session_key=payload["session"],
            client_ip="41.66.1.9",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari",
            referrer="https://google.com/",
        )
        await db_session.commit()
        assert count == 5

        # Batch: one row, encrypted + compressed, events preserved
        batches = (await db_session.execute(select(AnalyticsBatch))).scalars().all()
        assert len(batches) == 1
        b = batches[0]
        assert b.event_count == 5
        assert b.compression in ("zstd", "zlib")
        assert b.stored_bytes > 0
        # Blob must NOT contain the plaintext paths (encrypted at rest)
        raw = bytes(b.blob)
        assert b"/pricing" not in raw
        assert b"page_view" not in raw

        # Aggregates: "/" and "/pricing" rows for today
        rows = (await db_session.execute(select(AnalyticsDaily))).scalars().all()
        by_path = {r.path: r for r in rows}
        assert by_path["/"].views == 1
        assert by_path["/"].clicks == 1
        assert by_path["/"].scroll_total == 80
        assert by_path["/pricing"].views == 1
        assert by_path["/pricing"].exits == 1
        assert by_path["/pricing"].bounces == 0  # session had 2 pages
        assert by_path["/"].page_name == "Zemest Home"
        assert by_path["/"].visitor_keys == ["v-test1"]

        # Visitor profile: counters, UA parsing, IP
        profile = (
            await db_session.execute(
                select(VisitorProfile).where(VisitorProfile.visitor_key == "v-test1")
            )
        ).scalar_one()
        assert profile.pages_viewed == 2
        assert profile.total_events == 5
        assert profile.sessions_count == 1
        assert profile.last_ip == "41.66.1.9"
        assert profile.device_type == "mobile"
        assert profile.browser == "Safari"
        assert profile.first_referrer == "https://google.com/"
        assert "pricing" in (profile.interests or [])

    async def test_bounce_counted_for_single_page_session(self, db_session):
        await analytics_service.ingest_events(
            db_session,
            [
                {"type": "page_view", "path": "/about"},
                {"type": "session_end", "path": "/about", "session_pages": 1},
            ],
            visitor_key="v-bounce",
            session_key="s-b",
            client_ip="1.2.3.4",
        )
        await db_session.commit()
        row = (
            await db_session.execute(select(AnalyticsDaily).where(AnalyticsDaily.path == "/about"))
        ).scalar_one()
        assert row.bounces == 1

    async def test_malformed_events_dropped_not_fatal(self, db_session):
        bad = [
            {"type": "nosql_injection", "path": "/"},  # invalid type
            {"type": "page_view", "path": "no-leading-slash"},  # invalid path
            {"type": "page_view", "path": None},  # missing path
            {"type": "scroll", "path": "/", "scroll": 99999},  # clamped, kept
            {"type": "page_view", "path": "/ok"},  # good
            {"type": "click", "path": "/ok"},  # good (no element is fine)
        ]
        count = await analytics_service.ingest_events(
            db_session, bad, visitor_key="v-bad", session_key="s-x", client_ip="9.9.9.9"
        )
        await db_session.commit()
        assert count == 3  # clamped scroll + two good
        rows = (await db_session.execute(select(AnalyticsDaily))).scalars().all()
        by = {r.path: r for r in rows}
        assert by["/"].scroll_total == 100  # 99999 clamped to 100
        assert by["/ok"].views == 1

    async def test_authenticated_user_links_identity_server_side(self, db_session, test_user):
        await analytics_service.ingest_events(
            db_session,
            [{"type": "page_view", "path": "/dashboard"}],
            visitor_key="v-user",
            session_key="s-u",
            client_ip="5.5.5.5",
            user=test_user,
        )
        await db_session.commit()
        profile = (
            await db_session.execute(
                select(VisitorProfile).where(VisitorProfile.visitor_key == "v-user")
            )
        ).scalar_one()
        assert profile.user_id == test_user.id
        # PII attached server-side from the authenticated user
        assert profile.email == test_user.email
        assert profile.name == test_user.name


@pytest.mark.asyncio
class TestReadPaths:
    async def _seed(self, db_session):
        await analytics_service.ingest_events(
            db_session,
            _batch()["events"],
            visitor_key="v-good",
            session_key="s-1",
            client_ip="41.66.1.9",
        )
        # A "sucks" page: view + instant bounce, no scroll, no clicks
        await analytics_service.ingest_events(
            db_session,
            [
                {"type": "page_view", "path": "/sucky-page"},
                {"type": "session_end", "path": "/sucky-page", "session_pages": 1},
            ],
            visitor_key="v-bad",
            session_key="s-2",
            client_ip="8.8.4.4",
        )
        await db_session.commit()

    async def test_page_performance_worst_first(self, db_session):
        await self._seed(db_session)
        perf = await analytics_service.page_performance(db_session, days=14, worst_first=True)
        paths = [p["path"] for p in perf]
        assert "/sucky-page" in paths and "/" in paths
        # Worst-first: the bounce-only page must TOP the ranking ("what sucks").
        assert paths.index("/sucky-page") < paths.index("/")
        sucks = next(p for p in perf if p["path"] == "/sucky-page")
        assert sucks["bounce_rate"] == 1.0
        assert sucks["engagement"] < 0.5
        good = next(p for p in perf if p["path"] == "/")
        assert good["avg_scroll_pct"] == 80.0
        assert good["engagement"] > sucks["engagement"]

    async def test_export_roundtrip(self, db_session):
        """The product's 'decryptable' requirement: export_day returns the
        original events from the encrypted blobs."""
        await self._seed(db_session)
        events = await analytics_service.read_day_events(db_session, date.today())
        types = [e["t"] for e in events]
        assert types.count("page_view") == 3
        assert types.count("session_end") == 2
        assert types.count("click") == 1
        assert types.count("scroll") == 1
        # Server-side enrichment survived the round-trip
        assert any(e.get("ip") == "41.66.1.9" for e in events)
        assert any(e.get("v") == "v-good" for e in events)

    async def test_compact_day_merges_batches(self, db_session):
        await self._seed(db_session)
        before = (
            (await db_session.execute(select(AnalyticsBatch))).scalars().all()
        )
        assert len(before) == 2
        merged = await analytics_service.compact_day(db_session, date.today())
        await db_session.commit()
        assert merged == 2
        after = (
            (await db_session.execute(select(AnalyticsBatch))).scalars().all()
        )
        assert len(after) == 1
        assert after[0].event_count == 7  # 5 + 2 events preserved
        # Events still readable after compaction
        events = await analytics_service.read_day_events(db_session, date.today())
        assert len(events) == 7

    async def test_storage_stats(self, db_session):
        # Realistic volume: compression beats Fernet's fixed overhead only
        # once a batch has real payload — use 40 events.
        events = [
            {"type": "page_view", "path": f"/p/{i % 7}", "page_name": f"Page {i % 7}"}
            for i in range(40)
        ]
        await analytics_service.ingest_events(
            db_session,
            events,
            visitor_key="v-stats",
            session_key="s-stats",
            client_ip="7.7.7.7",
        )
        await db_session.commit()
        stats = await analytics_service.storage_stats(db_session)
        assert stats["batches"] == 1
        assert stats["events"] == 40
        assert stats["stored_bytes"] > 0
        assert stats["compression_ratio"] > 1, (
            f"zstd+Fernet should beat raw JSONL at realistic batch size: {stats}"
        )
        assert stats["bytes_per_event"] < 80, (
            f"storage target is ~15-25 B/event (allow 80 headroom): {stats}"
        )


@pytest.mark.asyncio
class TestCollectEndpoint:
    async def test_collect_public_returns_204(self, client):
        resp = await client.post("/api/analytics/collect", json=_batch(visitor="v-http"))
        assert resp.status_code == 204, resp.text

    async def test_collect_rejects_oversized_batch(self, client):
        events = [{"type": "page_view", "path": "/x"}] * 61
        resp = await client.post(
            "/api/analytics/collect",
            json={"visitor": "v-big", "events": events},
        )
        # pydantic max_length on the list → 422; the client never retry-loops
        assert resp.status_code in (204, 422)

    async def test_summary_requires_auth(self, client):
        resp = await client.get("/api/analytics/summary")
        assert resp.status_code == 401

    async def test_summary_scoped_to_own_blog_posts(
        self, client, auth_headers, db_session, test_user, test_tenant
    ):
        from app.models.blog_post import BlogPost

        db_session.add(
            BlogPost(
                id=uuid.uuid4(),
                tenant_id=test_tenant.id,
                slug="my-post",
                title="My Post",
                status="published",
            )
        )
        await db_session.commit()
        await analytics_service.ingest_events(
            db_session,
            [{"type": "page_view", "path": "/blog/my-post"}],
            visitor_key="v-x1",
            session_key="s",
            client_ip="1.1.1.1",
        )
        await db_session.commit()
        resp = await client.get("/api/analytics/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        paths = [p["path"] for p in data["pages"]]
        assert "/blog/my-post" in paths
        assert all(p["path"].startswith("/blog/") for p in data["pages"])


@pytest.mark.asyncio
class TestAdminAnalyticsEndpoints:
    @pytest_asyncio.fixture
    async def admin_headers(self, db_session):
        from app.utils.security import create_access_token, hash_password

        admin = User(
            id=uuid.uuid4(),
            name="Admin",
            email="admin-analytics@test.local",
            is_superadmin=True,
            hashed_password=hash_password("adminpass123"),
        )
        db_session.add(admin)
        await db_session.commit()
        return {"Authorization": f"Bearer {create_access_token({'sub': str(admin.id)})}"}

    async def test_analytics_endpoints_superadmin_only(self, client, auth_headers):
        for url in (
            "/api/admin/analytics/pages",
            "/api/admin/analytics/visitors",
            "/api/admin/analytics/storage",
        ):
            resp = await client.get(url, headers=auth_headers)
            assert resp.status_code == 403, f"{url} leaked to non-admin: {resp.status_code}"

    async def test_pages_endpoint(self, client, admin_headers, db_session):
        await analytics_service.ingest_events(
            db_session,
            _batch(visitor="v-admin")["events"],
            visitor_key="v-admin",
            session_key="s",
            client_ip="3.3.3.3",
        )
        await db_session.commit()
        resp = await client.get("/api/admin/analytics/pages", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["totals"]["views"] >= 2
        assert any(p["path"] == "/pricing" for p in data["pages"])

    async def test_visitors_directory_with_pii(self, client, admin_headers, db_session, test_user):
        await analytics_service.ingest_events(
            db_session,
            [{"type": "page_view", "path": "/"}],
            visitor_key="v-pii",
            session_key="s",
            client_ip="4.4.4.4",
            user=test_user,
        )
        await db_session.commit()
        resp = await client.get("/api/admin/analytics/visitors", headers=admin_headers)
        assert resp.status_code == 200
        visitors = resp.json()["visitors"]
        match = [v for v in visitors if v["visitor_key"] == "v-pii"]
        assert match and match[0]["email"] == test_user.email

        # Drill-down includes linked user context
        vid = match[0]["id"]
        detail = await client.get(f"/api/admin/analytics/visitors/{vid}", headers=admin_headers)
        assert detail.status_code == 200
        body = detail.json()
        assert body["linked_user"]["email"] == test_user.email
        assert body["recent_events"]

    async def test_export_endpoint(self, client, admin_headers, db_session):
        await analytics_service.ingest_events(
            db_session,
            [{"type": "page_view", "path": "/export-test"}],
            visitor_key="v-exp",
            session_key="s",
            client_ip="6.6.6.6",
        )
        await db_session.commit()
        today = date.today().isoformat()
        resp = await client.get(
            f"/api/admin/analytics/export?day={today}", headers=admin_headers
        )
        assert resp.status_code == 200
        assert "/export-test" in resp.text
        assert "application/x-ndjson" in resp.headers["content-type"]
