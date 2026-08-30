"""Tests for the social media scheduling module."""
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.models.scheduled_post import ScheduledPost


@pytest.mark.asyncio
class TestSchedulingEndpoints:

    async def test_schedule_text_post(self, client, auth_headers, test_tenant):
        """Test scheduling a text post to Facebook."""
        future_time = (datetime.utcnow() + timedelta(hours=2)).isoformat()
        resp = await client.post(
            f"/api/tenants/{test_tenant.id}/schedule/post",
            json={
                "platform": "facebook",
                "caption": "Special offer! 20% off all galabiyas today only! 🎉",
                "media_type": "text",
                "scheduled_at": future_time,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "scheduled"
        assert data["platform"] == "facebook"
        assert "id" in data

    async def test_schedule_photo_post(self, client, auth_headers, test_tenant):
        """Test scheduling a photo post."""
        future_time = (datetime.utcnow() + timedelta(hours=2)).isoformat()
        resp = await client.post(
            f"/api/tenants/{test_tenant.id}/schedule/post",
            json={
                "platform": "instagram",
                "caption": "New collection! Check out our latest designs ✨",
                "media_type": "photo",
                "media_urls": ["https://example.com/photo.jpg"],
                "scheduled_at": future_time,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201

    async def test_schedule_requires_future_time(self, client, auth_headers, test_tenant):
        """Scheduled time must be in the future."""
        past_time = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        resp = await client.post(
            f"/api/tenants/{test_tenant.id}/schedule/post",
            json={
                "platform": "facebook",
                "caption": "Test",
                "scheduled_at": past_time,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_schedule_invalid_platform(self, client, auth_headers, test_tenant):
        """Platform must be facebook or instagram."""
        future_time = (datetime.utcnow() + timedelta(hours=2)).isoformat()
        resp = await client.post(
            f"/api/tenants/{test_tenant.id}/schedule/post",
            json={
                "platform": "twitter",
                "caption": "Test",
                "scheduled_at": future_time,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_schedule_media_required_for_photo(self, client, auth_headers, test_tenant):
        """Photo posts require media_urls."""
        future_time = (datetime.utcnow() + timedelta(hours=2)).isoformat()
        resp = await client.post(
            f"/api/tenants/{test_tenant.id}/schedule/post",
            json={
                "platform": "facebook",
                "caption": "Test",
                "media_type": "photo",
                "scheduled_at": future_time,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_list_scheduled_posts(self, client, auth_headers, test_tenant, db_session):
        """Test listing scheduled posts."""
        # Create a post directly
        post = ScheduledPost(
            id=uuid.uuid4(),
            tenant_id=test_tenant.id,
            platform="facebook",
            caption="Test post",
            media_type="text",
            scheduled_at=datetime.utcnow() + timedelta(hours=2),
            status="scheduled",
        )
        db_session.add(post)
        await db_session.commit()

        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/schedule/posts",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(p["caption"] == "Test post" for p in data["posts"])

    async def test_cancel_scheduled_post(self, client, auth_headers, test_tenant, db_session):
        """Test cancelling a scheduled post."""
        post = ScheduledPost(
            id=uuid.uuid4(),
            tenant_id=test_tenant.id,
            platform="facebook",
            caption="To be cancelled",
            media_type="text",
            scheduled_at=datetime.utcnow() + timedelta(hours=2),
            status="scheduled",
        )
        db_session.add(post)
        await db_session.commit()

        resp = await client.patch(
            f"/api/tenants/{test_tenant.id}/schedule/posts/{post.id}/status",
            json={"status": "cancelled"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["new_status"] == "cancelled"

    async def test_delete_scheduled_post(self, client, auth_headers, test_tenant, db_session):
        """Test deleting a scheduled post."""
        post = ScheduledPost(
            id=uuid.uuid4(),
            tenant_id=test_tenant.id,
            platform="facebook",
            caption="To be deleted",
            media_type="text",
            scheduled_at=datetime.utcnow() + timedelta(hours=2),
            status="scheduled",
        )
        db_session.add(post)
        await db_session.commit()

        resp = await client.delete(
            f"/api/tenants/{test_tenant.id}/schedule/posts/{post.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    async def test_cannot_delete_published_post(self, client, auth_headers, test_tenant, db_session):
        """Cannot delete a post that's already published."""
        post = ScheduledPost(
            id=uuid.uuid4(),
            tenant_id=test_tenant.id,
            platform="facebook",
            caption="Published post",
            media_type="text",
            scheduled_at=datetime.utcnow() - timedelta(hours=2),
            published_at=datetime.utcnow() - timedelta(hours=1),
            status="published",
        )
        db_session.add(post)
        await db_session.commit()

        resp = await client.delete(
            f"/api/tenants/{test_tenant.id}/schedule/posts/{post.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
class TestSchedulingCrossTenant:

    async def test_other_tenant_posts_not_visible(self, client, auth_headers, test_tenant, db_session):
        """Posts from other tenants should not be visible."""
        # Create a post with a different tenant_id
        other_tenant_id = uuid.uuid4()
        post = ScheduledPost(
            id=uuid.uuid4(),
            tenant_id=other_tenant_id,
            platform="facebook",
            caption="Other tenant's post",
            media_type="text",
            scheduled_at=datetime.utcnow() + timedelta(hours=2),
            status="scheduled",
        )
        db_session.add(post)
        await db_session.commit()

        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/schedule/posts",
            headers=auth_headers,
        )
        data = resp.json()
        assert all(p["caption"] != "Other tenant's post" for p in data["posts"])
