"""Encrypted data vault: compression + AES-256-GCM round-trip, tamper
detection, key isolation, admin-only extraction.

Adversarial angles covered:
* round-trip fidelity (records -> sealed file -> extracted rows equal);
* a single flipped byte in the stored file is DETECTED (sha256 mismatch);
* even with the sha256 row recomputed to match tampered bytes, the GCM
  authentication tag still fails the extraction (defense in depth);
* the wrong master key cannot decrypt (per-file HKDF keys);
* archive files are written with 0600 permissions (owner-only);
* vault endpoints are superadmin-only (401 anon / 403 regular user / 200
  superadmin) — the plaintext never leaves the admin panel;
* the vault refuses to operate (loudly) without a configured master key.
"""
from __future__ import annotations

import os
import stat
import uuid
from datetime import datetime

import pytest

from app.config import get_settings
from app.models.vault import VaultFile
from app.services import vault as vault_service
from app.utils.security import hash_password

settings = get_settings()

MASTER_KEY = "8f" * 32  # 64 hex chars = 32 bytes
OTHER_KEY = "11" * 32


@pytest.fixture
def vault_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "VAULT_MASTER_KEY", MASTER_KEY)
    monkeypatch.setattr(settings, "VAULT_DIR", str(tmp_path / "vault"))
    yield settings


def _records(n: int = 50) -> list[dict]:
    return [
        {
            "user_id": str(uuid.uuid4()),
            "email": f"user{i}@example.com",
            "ip": f"41.10.20.{i % 255}",
            "dob": "1995-04-12",
            "chats": [f"message {j}" for j in range(20)],
        }
        for i in range(n)
    ]


# --------------------------------------------------------------------------- #
# Seal / open round-trip
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
class TestVaultRoundTrip:
    async def test_round_trip_preserves_records(self, db_session, vault_env):
        records = _records(50)
        vf = await vault_service.archive_records(
            db_session, "user_profiles", records
        )
        await db_session.commit()

        out = await vault_service.extract_records(db_session, vf)
        assert out["verified"] is True
        assert out["row_count"] == 50
        assert out["rows"] == records
        assert out["cipher"] == "aes-256-gcm"

    async def test_compression_actually_shrinks_data(self, db_session, vault_env):
        records = _records(200)  # repetitive JSON compresses very well
        vf = await vault_service.archive_records(
            db_session, "customer_profiles", records
        )
        await db_session.commit()
        assert vf.original_bytes > 1000
        assert vf.stored_bytes < vf.original_bytes * 0.5  # >2x smaller
        assert vf.row_count == 200

    async def test_files_are_owner_only(self, db_session, vault_env):
        vf = await vault_service.archive_records(db_session, "chat_archive", _records(3))
        await db_session.commit()
        mode = stat.S_IMODE(os.stat(vf.storage_path).st_mode)
        assert mode == 0o600

    async def test_index_row_integrity_fields(self, db_session, vault_env):
        records = _records(7)
        vf = await vault_service.archive_records(db_session, "user_profiles", records)
        await db_session.commit()
        blob = open(vf.storage_path, "rb").read()
        import hashlib

        assert vf.sha256 == hashlib.sha256(blob).hexdigest()
        assert vf.stored_bytes == len(blob)
        assert vf.codec in ("gzip", "zstd")

    async def test_empty_record_set_rejected(self, db_session, vault_env):
        with pytest.raises(vault_service.VaultError):
            await vault_service.archive_records(db_session, "analytics", [])

    async def test_missing_key_disables_vault(self, monkeypatch):
        monkeypatch.setattr(settings, "VAULT_MASTER_KEY", "")
        assert vault_service.vault_available() is False

    async def test_bad_master_key_format_rejected(self, monkeypatch):
        monkeypatch.setattr(settings, "VAULT_MASTER_KEY", "not-hex")
        assert vault_service.vault_available() is False


# --------------------------------------------------------------------------- #
# Tamper detection
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
class TestVaultTamperDetection:
    async def test_flipped_byte_detected_by_sha256(self, db_session, vault_env):
        vf = await vault_service.archive_records(db_session, "customer_profiles", _records(10))
        await db_session.commit()

        blob = bytearray(open(vf.storage_path, "rb").read())
        blob[-1] ^= 0xFF  # flip one byte in the ciphertext
        open(vf.storage_path, "wb").write(bytes(blob))

        with pytest.raises(vault_service.VaultError):
            await vault_service.extract_records(db_session, vf)

    async def test_gcm_tag_fails_even_with_fixed_hash(self, db_session, vault_env):
        vf = await vault_service.archive_records(db_session, "customer_profiles", _records(10))
        await db_session.commit()

        blob = bytearray(open(vf.storage_path, "rb").read())
        blob[-1] ^= 0xFF
        tampered = bytes(blob)
        open(vf.storage_path, "wb").write(tampered)

        # Attacker "fixes" the index hash to match the tampered bytes —
        # the GCM authentication tag must STILL reject the plaintext.
        import hashlib

        vf.sha256 = hashlib.sha256(tampered).hexdigest()
        db_session.add(vf)
        await db_session.flush()

        with pytest.raises(vault_service.VaultError) as exc:
            await vault_service.extract_records(db_session, vf)
        assert "authentication" in str(exc.value)

    async def test_wrong_master_key_cannot_decrypt(self, db_session, vault_env):
        vf = await vault_service.archive_records(db_session, "customer_profiles", _records(10))
        await db_session.commit()

        # Swap the key AFTER sealing.
        vault_env.VAULT_MASTER_KEY = OTHER_KEY
        with pytest.raises(vault_service.VaultError):
            await vault_service.extract_records(db_session, vf)

    async def test_missing_file_detected(self, db_session, vault_env):
        vf = await vault_service.archive_records(db_session, "customer_profiles", _records(5))
        await db_session.commit()
        os.unlink(vf.storage_path)
        with pytest.raises(vault_service.VaultError):
            await vault_service.extract_records(db_session, vf)


# --------------------------------------------------------------------------- #
# Admin-only endpoints (IDOR / authz)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
class TestVaultEndpoints:
    async def _superadmin(self, db_session):
        from app.models.user import User

        admin = User(
            id=uuid.uuid4(),
            name="Vault Admin",
            email=f"vault-admin-{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=hash_password("passw0rd123"),
            is_superadmin=True,
        )
        db_session.add(admin)
        await db_session.commit()
        from app.utils.security import create_access_token

        token = create_access_token({"sub": str(admin.id)})
        return {"Authorization": f"Bearer {token}"}

    async def test_anonymous_cannot_list_vault(self, client):
        resp = await client.get("/api/admin/vault")
        assert resp.status_code == 401

    async def test_regular_user_cannot_list_vault(self, client, auth_headers):
        resp = await client.get("/api/admin/vault", headers=auth_headers)
        assert resp.status_code == 403

    async def test_superadmin_lists_and_archives_and_extracts(
        self, client, db_session, vault_env, test_user, test_conversation
    ):
        headers = await self._superadmin(db_session)

        # Vault listing works and reports availability.
        resp = await client.get("/api/admin/vault", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["available"] is True

        # Chat archive over real seeded conversation data.
        resp = await client.post("/api/admin/vault/archive", headers=headers, json={
            "kind": "chat_archive",
        })
        assert resp.status_code == 201, resp.text
        archive = resp.json()
        assert archive["row_count"] >= 1
        file_id = archive["id"]

        # Extraction round-trips through the endpoint.
        resp = await client.get(f"/api/admin/vault/{file_id}/extract", headers=headers)
        assert resp.status_code == 200
        extracted = resp.json()
        assert extracted["verified"] is True
        assert extracted["kind"] == "chat_archive"
        assert any("messages" in row for row in extracted["rows"])

    async def test_regular_user_cannot_extract(self, client, auth_headers, vault_env):
        resp = await client.get(
            f"/api/admin/vault/{uuid.uuid4()}/extract", headers=auth_headers
        )
        assert resp.status_code == 403

    async def test_unknown_archive_kind_rejected(self, client, db_session, vault_env):
        headers = await self._superadmin(db_session)
        resp = await client.post("/api/admin/vault/archive", headers=headers, json={
            "kind": "not_a_kind",
        })
        assert resp.status_code == 422

    async def test_vault_unavailable_without_key(
        self, client, db_session, monkeypatch
    ):
        monkeypatch.setattr(settings, "VAULT_MASTER_KEY", "")
        headers = await self._superadmin(db_session)
        resp = await client.post("/api/admin/vault/archive", headers=headers, json={
            "kind": "chat_archive",
        })
        assert resp.status_code == 503
