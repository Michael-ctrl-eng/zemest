"""Python client for the Postiz API (sidecar social media scheduler).

Postiz is a full-featured open-source social media scheduler (35k★, AGPL-3.0)
running as a sidecar service in Docker. This client talks to its REST API to:
- Authenticate (cookie-based JWT, returned in `auth` header when NOT_SECURED)
- List connected integrations (FB Pages, IG accounts)
- Create/schedule posts
- Fetch analytics/insights
- Get best-time-to-post data

Architecture:
    ┌──────────────────────┐     ┌──────────────────────────┐
    │  Zemest (FastAPI)     │────▶│  Postiz (NestJS, :4007)  │
    │  app/scheduling/      │ API │  - FB/IG publishing       │
    │  postiz_client.py     │◀────│  - Insights              │
    └──────────────────────┘     │  - Best-time-to-post      │
                                 │  - AI caption generation  │
                                 └──────────────────────────┘

Postiz handles the heavy lifting of Graph API calls, token refresh,
Temporal workflow orchestration, and error handling. We delegate to it
and keep our own DB in sync for the dashboard.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Postiz runs as a sidecar at http://postiz:5000 (internal Docker network)
# or http://localhost:4007 (host port mapping for dev)
POSTIZ_BASE_URL = getattr(settings, "POSTIZ_URL", "http://localhost:4007")
POSTIZ_API_URL = f"{POSTIZ_BASE_URL}/api"


class PostizClient:
    """Async client for the Postiz REST API.

    Usage:
        client = PostizClient()
        await client.login("user@zemest.ai", "password")
        posts = await client.list_posts()
        await client.create_post(caption="Hello!", schedule_at="2026-01-01T10:00:00Z")
    """

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or POSTIZ_API_URL
        self._token: str | None = None
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> dict:
        """Build auth headers."""
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Cookie"] = f"auth={self._token}"
            headers["auth"] = self._token  # Postiz reads this when NOT_SECURED
        return headers

    # ============================================================
    # Auth
    # ============================================================

    async def login(self, email: str, password: str) -> bool:
        """Login to Postiz. Returns True on success.

        Postiz returns a JWT in the `auth` response header when NOT_SECURED
        is set (dev mode). In production (HTTPS), it sets an httpOnly cookie.
        """
        client = await self._get_client()
        try:
            resp = await client.post(
                "/auth/login",
                json={
                    "email": email,
                    "password": password,
                    "provider": "LOCAL",
                },
            )
            if resp.status_code == 200:
                # Try to get token from header (dev mode)
                self._token = resp.headers.get("auth")
                if not self._token:
                    # Production mode — token is in httpOnly cookie
                    # httpx will handle cookies automatically
                    pass
                logger.info("Postiz login successful")
                return True
            else:
                logger.error(f"Postiz login failed: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Postiz login error: {e}")
            return False

    async def register(self, email: str, password: str, name: str = "") -> bool:
        """Register a new Postiz account. Returns True on success."""
        client = await self._get_client()
        try:
            resp = await client.post(
                "/auth/register",
                json={
                    "email": email,
                    "password": password,
                    "name": name,
                    "provider": "LOCAL",
                },
            )
            if resp.status_code == 200:
                self._token = resp.headers.get("auth")
                return True
            return False
        except Exception as e:
            logger.error(f"Postiz register error: {e}")
            return False

    async def check_can_register(self) -> bool:
        """Check if registration is enabled on the Postiz instance."""
        client = await self._get_client()
        try:
            resp = await client.get("/auth/can-register")
            data = resp.json()
            return data.get("register", False)
        except Exception:
            return False

    # ============================================================
    # Integrations (connected social accounts)
    # ============================================================

    async def list_integrations(self) -> list[dict]:
        """List all connected social integrations (FB Pages, IG accounts, etc.).

        Returns list of dicts with: id, identifier (display name), name,
        provider (facebook, instagram, etc.), profilePictureUrl.
        """
        client = await self._get_client()
        try:
            resp = await client.get("/integrations", headers=self._headers())
            if resp.status_code == 200:
                data = resp.json()
                return data.get("integrations", [])
            return []
        except Exception as e:
            logger.error(f"Postiz list_integrations error: {e}")
            return []

    async def get_connect_url(self, provider: str) -> str | None:
        """Get the OAuth URL to connect a social account.

        Args:
            provider: 'facebook', 'instagram', 'instagram_standalone', etc.

        Returns:
            OAuth URL to redirect the user to, or None on error.
        """
        client = await self._get_client()
        try:
            resp = await client.post(
                f"/integrations/social-connect/{provider}",
                headers=self._headers(),
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("url") or data.get("oauthUrl")
            return None
        except Exception as e:
            logger.error(f"Postiz get_connect_url error: {e}")
            return None

    # ============================================================
    # Posts (create, list, schedule, delete)
    # ============================================================

    async def create_post(
        self,
        posts: list[dict],
        schedule_at: str | None = None,
        group_id: str | None = None,
    ) -> dict | None:
        """Create one or more scheduled posts.

        Args:
            posts: List of post payloads. Each post has:
                - integrationId: str (from list_integrations)
                - content: str (caption text)
                - mediaUrls: list[str] (public URLs)
                - settings: dict (platform-specific)
            schedule_at: ISO datetime string (UTC). If None, posts are drafts.
            group_id: Optional group ID for batch posts.

        Returns:
            Created post object or None on error.
        """
        client = await self._get_client()
        payload = {
            "posts": posts,
            "type": "draft" if schedule_at is None else "schedule",
            "date": schedule_at,
        }
        if group_id:
            payload["group"] = group_id

        try:
            resp = await client.post("/posts", json=payload, headers=self._headers())
            if resp.status_code in (200, 201):
                return resp.json()
            logger.error(f"Postiz create_post failed: {resp.status_code} {resp.text}")
            return None
        except Exception as e:
            logger.error(f"Postiz create_post error: {e}")
            return None

    async def list_posts(
        self,
        page: int = 1,
        limit: int = 50,
        filter_type: str = "scheduled",
    ) -> dict | None:
        """List posts with pagination.

        Args:
            filter_type: 'scheduled', 'published', 'draft', 'failed'

        Returns: {"posts": [...], "total": int, "page": int}
        """
        client = await self._get_client()
        try:
            resp = await client.get(
                "/posts",
                params={"page": page, "limit": limit, "type": filter_type},
                headers=self._headers(),
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.error(f"Postiz list_posts error: {e}")
            return None

    async def get_post(self, post_id: str) -> dict | None:
        """Get a single post by ID."""
        client = await self._get_client()
        try:
            resp = await client.get(f"/posts/{post_id}", headers=self._headers())
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.error(f"Postiz get_post error: {e}")
            return None

    async def delete_post(self, group_id: str) -> bool:
        """Delete a post (by group ID)."""
        client = await self._get_client()
        try:
            resp = await client.delete(f"/posts/{group_id}", headers=self._headers())
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Postiz delete_post error: {e}")
            return False

    async def update_post_date(
        self,
        post_id: str,
        new_date: str,
        action: str = "update",
    ) -> bool:
        """Reschedule a post to a new date.

        Args:
            action: 'schedule' (requeue) or 'update' (just change the date)
        """
        client = await self._get_client()
        try:
            resp = await client.put(
                f"/posts/{post_id}/date",
                json={"date": new_date, "action": action},
                headers=self._headers(),
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Postiz update_post_date error: {e}")
            return False

    async def find_free_slot(self, integration_id: str | None = None) -> str | None:
        """Find the next free time slot for posting.

        Returns ISO datetime string.
        """
        client = await self._get_client()
        url = "/posts/find-slot"
        if integration_id:
            url += f"/{integration_id}"
        try:
            resp = await client.get(url, headers=self._headers())
            if resp.status_code == 200:
                return resp.json().get("date")
            return None
        except Exception as e:
            logger.error(f"Postiz find_free_slot error: {e}")
            return None

    # ============================================================
    # Analytics / Insights
    # ============================================================

    async def get_post_statistics(self, post_id: str) -> dict | None:
        """Get statistics/insights for a specific post.

        Returns metrics like: impressions, reach, engagement, likes, comments, shares.
        """
        client = await self._get_client()
        try:
            resp = await client.get(
                f"/posts/{post_id}/statistics", headers=self._headers()
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.error(f"Postiz get_post_statistics error: {e}")
            return None

    # ============================================================
    # AI Post Generation (Postiz's built-in AI)
    # ============================================================

    async def generate_posts(
        self,
        prompt: str,
        number_of_posts: int = 3,
        platforms: list[str] | None = None,
    ) -> list[dict] | None:
        """Use Postiz's built-in AI to generate post ideas.

        Postiz streams results — this method collects them all.

        Args:
            prompt: What to write about
            number_of_posts: How many variants
            platforms: Which platforms to optimize for

        Returns: List of generated post dicts.
        """
        client = await self._get_client()
        payload = {
            "prompt": prompt,
            "numberOfPosts": number_of_posts,
            "integrations": platforms or [],
        }

        try:
            # Postiz uses streaming for generation
            import json as _json
            results = []
            async with client.stream(
                "POST", "/posts/generator", json=payload, headers=self._headers()
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            event = _json.loads(line)
                            if event.get("name") == "result":
                                results.append(event)
                        except _json.JSONDecodeError:
                            continue
            return results if results else None
        except Exception as e:
            logger.error(f"Postiz generate_posts error: {e}")
            return None

    # ============================================================
    # Health check
    # ============================================================

    async def health_check(self) -> bool:
        """Check if the Postiz sidecar is running and reachable."""
        client = await self._get_client()
        try:
            # Postiz frontend is at the root URL
            base_client = httpx.AsyncClient(
                base_url=POSTIZ_BASE_URL, timeout=5.0
            )
            resp = await base_client.get("/")
            await base_client.aclose()
            return resp.status_code == 200
        except Exception:
            return False


# ============================================================
# Singleton client for app-wide use
# ============================================================

_postiz_client: PostizClient | None = None


def get_postiz_client() -> PostizClient:
    """Get the singleton PostizClient instance."""
    global _postiz_client
    if _postiz_client is None:
        _postiz_client = PostizClient()
    return _postiz_client
