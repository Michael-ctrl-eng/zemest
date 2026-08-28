"""Tests for crawl endpoints."""
from unittest.mock import patch, AsyncMock

import pytest


@pytest.mark.asyncio
class TestCrawl:

    @patch("app.api.crawl._run_crawl_inline", new_callable=AsyncMock)
    async def test_start_crawl_job(self, mock_run, client, auth_headers, test_tenant):
        resp = await client.post(
            f"/api/tenants/{test_tenant.id}/crawl",
            json={"url": "https://teststore.com", "depth": 2},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["url"] == "https://teststore.com"
        assert data["status"] == "pending"

    @patch("app.api.crawl._run_crawl_inline", new_callable=AsyncMock)
    async def test_list_crawl_jobs(self, mock_run, client, auth_headers, test_tenant):
        # Create a job first
        await client.post(
            f"/api/tenants/{test_tenant.id}/crawl",
            json={"url": "https://example.com", "depth": 1},
            headers=auth_headers,
        )

        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/crawl/jobs",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        jobs = resp.json()
        assert len(jobs) >= 1

    @patch("app.api.crawl._run_crawl_inline", new_callable=AsyncMock)
    async def test_get_crawl_job_detail(self, mock_run, client, auth_headers, test_tenant):
        # Create a job
        create_resp = await client.post(
            f"/api/tenants/{test_tenant.id}/crawl",
            json={"url": "https://example.com", "depth": 1},
            headers=auth_headers,
        )
        job_id = create_resp.json()["id"]

        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/crawl/jobs/{job_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    async def test_crawl_job_not_found(self, client, auth_headers, test_tenant):
        import uuid
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/crawl/jobs/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert resp.status_code == 404
