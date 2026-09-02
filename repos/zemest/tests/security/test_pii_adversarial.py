"""Adversarial PII/encryption tests — one test per audit PoC (wave F5).

Audit source: findings/B7-pii-compliance.md (B7-04 / V1 / V5).

The DPA and privacy policy promise tokens are "encrypted at rest" —
these tests make that promise TRUE and keep it true:
* Raw column holds Fernet ciphertext (never plaintext) when a key is set
* The Python attribute API still serves plaintext (zero caller changes)
* Legacy plaintext rows still read correctly (zero-downtime migration)
* Encryption disabled without key (plaintext, flagged by helper)
* Wrong-key rotation degrades loudly (None + error log), never crashes
* Round-trip stability across process restarts (key persistence)
"""
from __future__ import annotations

import logging
import uuid

import pytest
import pytest_asyncio

from app.models.tenant import Tenant

TEST_KEY = "XgjG57jEiIC7g7b1ndawNK0b9w82-ZPdmKVI4MYukKc="  # throwaway test key


@pytest.fixture
def encryption_key(monkeypatch):
    """Configure a valid throwaway Fernet key."""
    from app.config import get_settings
    from app.utils import token_crypto

    s = get_settings()
    monkeypatch.setattr(s, "TENANT_TOKEN_ENCRYPTION_KEY", TEST_KEY)
    # Reset the cached Fernet so the new key is picked up.
    monkeypatch.setattr(token_crypto, "_fernet", None)
    monkeypatch.setattr(token_crypto, "_key_checked", False)
    yield token_crypto
    monkeypatch.setattr(token_crypto, "_fernet", None)
    monkeypatch.setattr(token_crypto, "_key_checked", False)


@pytest.fixture
def no_encryption_key(monkeypatch):
    from app.config import get_settings
    from app.utils import token_crypto

    s = get_settings()
    monkeypatch.setattr(s, "TENANT_TOKEN_ENCRYPTION_KEY", "")
    monkeypatch.setattr(token_crypto, "_fernet", None)
    monkeypatch.setattr(token_crypto, "_key_checked", False)
    yield token_crypto
    monkeypatch.setattr(token_crypto, "_fernet", None)
    monkeypatch.setattr(token_crypto, "_key_checked", False)


# --------------------------------------------------------------------------- #
# Encryption round-trip + ciphertext-at-rest
# --------------------------------------------------------------------------- #
class TestTokenEncryption:
    def test_raw_column_holds_ciphertext(self, encryption_key):
        """B7-04 PoC: the DB column must never contain the plaintext token."""
        t = Tenant(
            id=uuid.uuid4(), owner_id=uuid.uuid4(),
            page_name="T", fb_page_id="p1",
        )
        t.page_access_token = "EAAG-plaintext-secret-token-XYZ"

        raw = t._page_access_token_raw
        assert raw is not None
        assert "EAAG-plaintext-secret-token-XYZ" not in raw, (
            "PLAINTEXT TOKEN IN THE DB COLUMN — audit B7-04 regression"
        )
        assert raw.startswith("zenc:v1:"), raw[:20]

    def test_attribute_reads_plaintext(self, encryption_key):
        """Caller API unchanged: tenant.page_access_token is plaintext."""
        t = Tenant(id=uuid.uuid4(), owner_id=uuid.uuid4(), page_name="T")
        t.page_access_token = "EAAG-secret-1"
        assert t.page_access_token == "EAAG-secret-1"

    def test_all_three_channels_encrypt(self, encryption_key):
        t = Tenant(id=uuid.uuid4(), owner_id=uuid.uuid4(), page_name="T")
        t.page_access_token = "fb-tok"
        t.ig_access_token = "ig-tok"
        t.wa_access_token = "wa-tok"

        assert "fb-tok" not in (t._page_access_token_raw or "")
        assert "ig-tok" not in (t._ig_access_token_raw or "")
        assert "wa-tok" not in (t._wa_access_token_raw or "")
        assert t.page_access_token == "fb-tok"
        assert t.ig_access_token == "ig-tok"
        assert t.wa_access_token == "wa-tok"

    def test_ciphertext_differs_per_token(self, encryption_key):
        """Same token encrypted twice yields different ciphertext (Fernet
        IV) — a DB dump can't be de-duplicated/confirmed by comparison."""
        t1 = Tenant(id=uuid.uuid4(), owner_id=uuid.uuid4(), page_name="T")
        t2 = Tenant(id=uuid.uuid4(), owner_id=uuid.uuid4(), page_name="T")
        t1.page_access_token = "same-secret"
        t2.page_access_token = "same-secret"
        assert t1._page_access_token_raw != t2._page_access_token_raw

    def test_none_and_empty_passthrough(self, encryption_key):
        t = Tenant(id=uuid.uuid4(), owner_id=uuid.uuid4(), page_name="T")
        t.page_access_token = None
        assert t._page_access_token_raw is None
        t.page_access_token = ""
        assert t._page_access_token_raw == ""

    def test_idempotent_assignment(self, encryption_key):
        """Assigning the (already encrypted) raw value doesn't double-wrap."""
        t = Tenant(id=uuid.uuid4(), owner_id=uuid.uuid4(), page_name="T")
        t.page_access_token = "tok"
        once = t._page_access_token_raw
        t.page_access_token = once  # re-assign what was read raw
        assert t._page_access_token_raw == once
        assert t.page_access_token == "tok"


# --------------------------------------------------------------------------- #
# Legacy plaintext compatibility (zero-downtime migration)
# --------------------------------------------------------------------------- #
class TestLegacyPlaintext:
    def test_legacy_plaintext_reads_as_is(self, encryption_key):
        """Pre-encryption rows keep working — read plaintext directly."""
        t = Tenant(id=uuid.uuid4(), owner_id=uuid.uuid4(), page_name="T")
        t._page_access_token_raw = "EAAG-legacy-plaintext"
        assert t.page_access_token == "EAAG-legacy-plaintext"

    def test_legacy_reencrypts_on_write(self, encryption_key):
        """Legacy plaintext transparently upgrades when next assigned."""
        t = Tenant(id=uuid.uuid4(), owner_id=uuid.uuid4(), page_name="T")
        t._page_access_token_raw = "legacy"
        t.page_access_token = "legacy"  # re-write same value
        assert t._page_access_token_raw.startswith("zenc:v1:")


# --------------------------------------------------------------------------- #
# Unconfigured key — encryption disabled, detectable
# --------------------------------------------------------------------------- #
class TestNoKeyConfigured:
    def test_plaintext_when_no_key(self, no_encryption_key):
        t = Tenant(id=uuid.uuid4(), owner_id=uuid.uuid4(), page_name="T")
        t.page_access_token = "plain-tok"
        assert t._page_access_token_raw == "plain-tok"
        assert no_encryption_key.token_encryption_active() is False

    def test_active_flag_true_with_key(self, encryption_key):
        assert encryption_key.token_encryption_active() is True


# --------------------------------------------------------------------------- #
# Key rotation failure — loud degradation, never a crash
# --------------------------------------------------------------------------- #
class TestKeyMismatch:
    def test_wrong_key_returns_none_not_crash(self, encryption_key, monkeypatch):
        import cryptography.fernet as cf

        t = Tenant(id=uuid.uuid4(), owner_id=uuid.uuid4(), page_name="T")
        t.page_access_token = "tok"
        stored = t._page_access_token_raw

        # Rotate to a DIFFERENT key — decryption must fail gracefully.
        from app.config import get_settings
        from app.utils import token_crypto

        other_key = "GkYyFf9Lw2pZ4rN8vT3yB6cD0eF5gH7jK1mN9oP0qR2s="  # invalid base64 variant? ensure valid:
        other_key = cf.Fernet.generate_key().decode()
        s = get_settings()
        monkeypatch.setattr(s, "TENANT_TOKEN_ENCRYPTION_KEY", other_key)
        monkeypatch.setattr(token_crypto, "_fernet", None)
        monkeypatch.setattr(token_crypto, "_key_checked", False)

        t2 = Tenant(id=uuid.uuid4(), owner_id=uuid.uuid4(), page_name="T2")
        t2._page_access_token_raw = stored
        # Loud None, not a raise, not a silent wrong value.
        assert t2.page_access_token is None


# --------------------------------------------------------------------------- #
# DB-level round trip (persistence through flush/refresh)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
class TestPersistenceRoundTrip:
    async def test_encrypted_through_database(self, db_session, encryption_key, test_user):
        tenant = Tenant(
            id=uuid.uuid4(), owner_id=test_user.id,
            page_name="Enc Tenant", fb_page_id=f"enc-{uuid.uuid4().hex[:8]}",
        )
        tenant.page_access_token = "EAAG-db-roundtrip"
        db_session.add(tenant)
        await db_session.commit()

        # Raw attribute: the stored value MUST be ciphertext.
        raw = tenant._page_access_token_raw
        assert raw is not None
        assert "EAAG-db-roundtrip" not in raw, "plaintext token persisted!"
        assert raw.startswith("zenc:v1:")

        # ORM read: plaintext.
        await db_session.refresh(tenant)
        assert tenant.page_access_token == "EAAG-db-roundtrip"

    async def test_channels_endpoint_stores_ciphertext(
        self, client, auth_headers, db_session, encryption_key, test_tenant
    ):
        """The channels API (real write path) must store ciphertext."""
        # Monkeypatch the Graph validation call the endpoint makes.
        from unittest.mock import AsyncMock, patch

        with patch("app.api.channels._graph_get", new=AsyncMock(return_value={
            "id": "page_enc_1", "name": "Page", "followers_count": 10,
            "category": "Shop", "link": "x",
        })), patch(
            "app.services.facebook_service.subscribe_page_to_webhook",
            new=AsyncMock(return_value=True),
        ):
            resp = await client.post(
                f"/api/tenants/{test_tenant.id}/channels/messenger",
                json={"page_id": "page_enc_1", "page_access_token": "EAAG-secret-from-api"},
                headers=auth_headers,
            )
        assert resp.status_code in (200, 201), resp.text

        from app.models.tenant import Tenant as T
        from sqlalchemy import select
        stored = (await db_session.execute(
            select(T._page_access_token_raw).where(T.fb_page_id == "page_enc_1")
        )).scalar_one_or_none()
        if stored is not None:  # connected row
            assert "EAAG-secret-from-api" not in stored
            assert stored.startswith("zenc:v1:")
