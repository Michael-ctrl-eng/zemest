"""Tests for authentication endpoints."""
import pytest
import pytest_asyncio


@pytest.mark.asyncio
class TestAuth:
    """Test auth registration, login, and JWT flow."""

    async def test_register_new_user(self, client):
        """Registration returns a uniform 202 ack — no tokens, no enumeration."""
        resp = await client.post("/api/auth/register", json={
            "name": "Rahim Miah",
            "email": "rahim@example.com",
            "password": "securepass123",
        })
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "accepted"
        # Anti-enumeration: no token in the register response at all.
        assert "access_token" not in data
        # The account is usable: login works right away.
        login = await client.post("/api/auth/login", json={
            "email": "rahim@example.com",
            "password": "securepass123",
        })
        assert login.status_code == 200
        assert "access_token" in login.json()
        assert "refresh_token" in login.json()

    async def test_register_duplicate_email(self, client, test_user):
        """Duplicate registration is INDISTINGUISHABLE from success.

        Audit PoC (F1 anti-enumeration): the old endpoint returned
        400 "Email already registered" — a free oracle for harvesting
        registered addresses. Both paths must return 202 + identical body.
        """
        resp = await client.post("/api/auth/register", json={
            "name": "Another User",
            "email": "test@example.com",  # Same as test_user
            "password": "pass12345",
        })
        assert resp.status_code == 202
        assert resp.json()["status"] == "accepted"
        assert "already registered" not in resp.json().get("message", "")

    async def test_register_short_password_rejected(self, client):
        """Password policy: minimum 8 characters (NIST-aligned length rule)."""
        resp = await client.post("/api/auth/register", json={
            "name": "Weak Password",
            "email": "weakpw@example.com",
            "password": "short",  # 5 chars
        })
        assert resp.status_code == 422

    async def test_register_invalid_email(self, client):
        resp = await client.post("/api/auth/register", json={
            "name": "Bad Email",
            "email": "not-an-email",
            "password": "pass123",
        })
        assert resp.status_code == 422

    async def test_login_valid_credentials(self, client, test_user):
        resp = await client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_login_wrong_password(self, client, test_user):
        resp = await client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client):
        resp = await client.post("/api/auth/login", json={
            "email": "nobody@example.com",
            "password": "pass123",
        })
        assert resp.status_code == 401

    async def test_get_me_authenticated(self, client, test_user, auth_headers):
        resp = await client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test User"
        assert data["email"] == "test@example.com"

    async def test_get_me_no_token(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_get_me_invalid_token(self, client):
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"},
        )
        assert resp.status_code == 401
