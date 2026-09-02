"""F5 at-rest token encryption adversarial tests (audit A4-H4).

Verifies:
- Tokens written through the ORM come back as plaintext in Python but are
  Fernet ciphertext at the storage layer.
- A raw DB read (what an attacker with a dump/backup sees) yields NO
  usable token.
- Legacy plaintext rows still read correctly (graceful migration).
- Corrupted ciphertext fails closed (reads as missing, never crashes).
- Wrong key fails closed instead of returning garbage.
"""
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from app.models.tenant import Tenant
from app.utils.token_crypto import decrypt_token, encrypt_token, is_encrypted


@pytest.mark.asyncio
class TestTokenEncryption:
    async def test_orm_roundtrip_and_storage_ciphertext(self, db_session, test_user):
        """Write via ORM → read back the plaintext; the stored bytes are
        NOT the plaintext."""
        token = "EAAG-page-token-SUPERSECRET-1234567890"
        tenant = Tenant(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            page_name="Token Crypto Store",
            fb_page_id=f"page_{uuid.uuid4().hex[:8]}",
            page_access_token=token,
        )
        db_session.add(tenant)
        await db_session.flush()

        # ORM read: transparent decryption
        assert tenant.page_access_token == token

        # Raw storage read: what a DB dump / stolen backup contains
        raw = (
            await db_session.execute(
                sa.text(
                    "SELECT page_access_token FROM tenants WHERE id = :id"
                ),
                {"id": tenant.id.hex},
            )
        ).scalar_one()
        assert raw != token, "token stored in PLAINTEXT at rest"
        assert is_encrypted(raw)
        assert "SUPERSECRET" not in raw

    async def test_all_token_columns_encrypted(self, db_session, test_user):
        tenant = Tenant(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            page_name="Multi Channel",
            fb_page_id=f"page_{uuid.uuid4().hex[:8]}",
            page_access_token="PAGE-TOKEN-XYZ",
            ig_access_token="IG-TOKEN-XYZ",
            wa_access_token="WA-TOKEN-XYZ",
            postiz_token="POSTIZ-JWT-XYZ",
        )
        db_session.add(tenant)
        await db_session.flush()

        raw_row = (
            await db_session.execute(
                sa.text(
                    "SELECT page_access_token, ig_access_token, wa_access_token, "
                    "postiz_token FROM tenants WHERE id = :id"
                ),
                {"id": tenant.id.hex},
            )
        ).mappings().one()

        for col, secret in (
            ("page_access_token", "PAGE-TOKEN-XYZ"),
            ("ig_access_token", "IG-TOKEN-XYZ"),
            ("wa_access_token", "WA-TOKEN-XYZ"),
            ("postiz_token", "POSTIZ-JWT-XYZ"),
        ):
            assert secret not in raw_row[col], f"{col} stored in plaintext"
            assert is_encrypted(raw_row[col])

        # And all still roundtrip through the ORM
        assert tenant.page_access_token == "PAGE-TOKEN-XYZ"
        assert tenant.wa_access_token == "WA-TOKEN-XYZ"

    async def test_legacy_plaintext_row_still_reads(self, db_session, test_user):
        """Rows written before this fix keep working — no forced downtime."""
        legacy_token = "LEGACY-PLAINTEXT-TOKEN"
        tenant = Tenant(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            page_name="Legacy Store",
            fb_page_id=f"page_{uuid.uuid4().hex[:8]}",
        )
        db_session.add(tenant)
        await db_session.flush()
        tenant_hex = tenant.id.hex

        # Simulate a pre-fix write: raw plaintext straight into the column.
        await db_session.execute(
            sa.text(
                "UPDATE tenants SET page_access_token = :t WHERE id = :id"
            ),
            {"t": legacy_token, "id": tenant_hex},
        )
        # Raw read (what the EncryptedText result-value hook receives)
        raw = (
            await db_session.execute(
                sa.text(
                    "SELECT page_access_token FROM tenants WHERE id = :id"
                ),
                {"id": tenant_hex},
            )
        ).scalar_one()
        # Legacy passthrough: plaintext rows decrypt to themselves
        assert raw == legacy_token
        assert decrypt_token(raw) == legacy_token
        assert not is_encrypted(raw)


class TestTokenCryptoUnit:
    def test_encrypt_decrypt_roundtrip(self):
        original = "EAAG" + "x" * 200
        stored = encrypt_token(original)
        assert stored != original
        assert is_encrypted(stored)
        assert decrypt_token(stored) == original

    def test_double_encryption_is_noop(self):
        original = "once-is-enough"
        once = encrypt_token(original)
        assert encrypt_token(once) == once

    def test_none_and_empty_passthrough(self):
        assert encrypt_token(None) is None
        assert encrypt_token("") == ""
        assert decrypt_token(None) is None

    def test_corrupted_ciphertext_fails_closed(self):
        stored = encrypt_token("real-token")
        corrupted = stored[:20] + "XXXX" + stored[24:]
        assert decrypt_token(corrupted) is None, (
            "corrupted ciphertext must read as MISSING, never crash or leak"
        )

    def test_wrong_key_fails_closed(self):
        """A rotated/incorrect key must not return garbage."""
        from app.utils import token_crypto
        stored = encrypt_token("real-token")
        # Simulate key rotation: force a different fernet instance
        import base64, hashlib
        from cryptography.fernet import Fernet
        old = token_crypto._fernet
        try:
            token_crypto._fernet = Fernet(
                base64.urlsafe_b64encode(hashlib.sha256(b"another-key").digest())
            )
            assert decrypt_token(stored) is None
        finally:
            token_crypto._fernet = old

    def test_plaintext_detection(self):
        assert not is_encrypted("plain-token")
        assert not is_encrypted(None)
        assert is_encrypted(encrypt_token("secret"))
