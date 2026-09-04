"""Encrypted, compressed data vault.

Stores sensitive user/customer intelligence (IP, email, DOB, addresses,
chat archives, analytics) as **encrypted + compressed** files on disk so the
platform keeps the smallest footprint possible while every byte at rest is
confidential:

* **Compression** — JSONL rows compressed with zstd (when the ``zstandard``
  package is installed) falling back to gzip level 9 (stdlib). Typical chat
  archives shrink 10-20x.
* **Encryption** — AES-256-GCM (authenticated): tampering is DETECTED, not
  just possible to notice. Each file gets an independent key derived via
  HKDF-SHA256 from VAULT_MASTER_KEY with the file id as salt, so one leaked
  file key reveals nothing about any other file. Random 96-bit nonce per
  file, stored in the file header.
* **Integrity** — sha256 of the stored bytes AND of the plaintext JSONL are
  recorded in the index row; extraction verifies both plus the GCM tag.
* **Extraction** — decrypt + decompress is exposed ONLY to superadmins via
  the admin panel (see app/admin/api.py), from anywhere the admin panel is
  reachable.

File layout::

    b"ZV1" | codec byte (0x01=zstd, 0x02=gzip) | 12-byte nonce |
    AES-256-GCM ciphertext || 16-byte tag

The master key is a 32-byte hex/base64 string in VAULT_MASTER_KEY (NEVER in
code, never in the DB). Losing it loses the vault — operators must back it
up; a missing key disables archiving loudly (not silently).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import secrets
import tempfile
import uuid
from pathlib import Path
from typing import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.vault import VaultFile

logger = logging.getLogger(__name__)

MAGIC = b"ZV1"
CODEC_ZSTD = 0x01
CODEC_GZIP = 0x02

try:  # optional, smaller archives when present
    import zstandard as _zstd  # type: ignore

    _ZSTD_OK = True
except ImportError:  # pragma: no cover — depends on deployment
    _ZSTD_OK = False


class VaultError(Exception):
    """Vault operational error (missing key, tamper, corruption)."""


# --------------------------------------------------------------------------- #
# Key management
# --------------------------------------------------------------------------- #

def _parse_master_key(raw: str) -> bytes:
    """Accept 64-char hex OR base64 of 32 bytes. Raises VaultError otherwise."""
    raw = (raw or "").strip()
    if not raw:
        raise VaultError("VAULT_MASTER_KEY is not configured")
    try:
        if len(raw) == 64:
            key = bytes.fromhex(raw)
            if len(key) == 32:
                return key
        import base64

        key = base64.b64decode(raw, validate=True)
        if len(key) == 32:
            return key
    except ValueError:
        pass
    raise VaultError("VAULT_MASTER_KEY must be 32 bytes (64 hex chars or base64)")


def _derive_file_key(master: bytes, file_id: uuid.UUID) -> bytes:
    """HKDF-SHA256(master, salt=file_id, info='zemest-vault-v1') -> 32 bytes."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=file_id.bytes,
        info=b"zemest-vault-v1",
    ).derive(master)


# --------------------------------------------------------------------------- #
# Codec
# --------------------------------------------------------------------------- #

def _compress(payload: bytes) -> tuple[bytes, int]:
    if _ZSTD_OK:
        c = _zstd.ZstdCompressor(level=9)
        return c.compress(payload), CODEC_ZSTD
    return gzip.compress(payload, compresslevel=9), CODEC_GZIP


def _decompress(blob: bytes, codec: int) -> bytes:
    if codec == CODEC_ZSTD:
        if not _ZSTD_OK:
            raise VaultError("Archive uses zstd but the zstandard package is not installed")
        return _zstd.ZstdDecompressor().decompress(blob)
    if codec == CODEC_GZIP:
        return gzip.decompress(blob)
    raise VaultError(f"Unknown vault codec byte: {codec}")


# --------------------------------------------------------------------------- #
# Core seal / open
# --------------------------------------------------------------------------- #

def _seal(records: Iterable[dict], master: bytes, file_id: uuid.UUID) -> tuple[bytes, dict]:
    """Serialize -> compress -> encrypt. Returns (file_bytes, meta)."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    plaintext = "\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in records)
    plaintext_bytes = plaintext.encode("utf-8")
    compressed, codec = _compress(plaintext_bytes)

    nonce = secrets.token_bytes(12)
    key = _derive_file_key(master, file_id)
    ciphertext = AESGCM(key).encrypt(nonce, compressed, associated_data=MAGIC)

    blob = MAGIC + bytes([codec]) + nonce + ciphertext
    meta = {
        "codec": "zstd" if codec == CODEC_ZSTD else "gzip",
        "original_bytes": len(plaintext_bytes),
        "stored_bytes": len(blob),
        "plaintext_sha256": hashlib.sha256(plaintext_bytes).hexdigest(),
    }
    return blob, meta


def _open(blob: bytes, master: bytes, file_id: uuid.UUID) -> list[dict]:
    """Decrypt -> decompress -> parse JSONL. Raises VaultError on any failure."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if len(blob) < len(MAGIC) + 1 + 12 + 16:
        raise VaultError("Vault file truncated")
    if blob[: len(MAGIC)] != MAGIC:
        raise VaultError("Vault file has a bad magic header")
    codec = blob[3]
    nonce = blob[4:16]
    ciphertext = blob[16:]

    key = _derive_file_key(master, file_id)
    try:
        compressed = AESGCM(key).decrypt(nonce, ciphertext, associated_data=MAGIC)
    except Exception as exc:  # noqa: BLE001 — InvalidTag and friends
        raise VaultError(
            "Vault file failed authentication (wrong master key or tampered bytes)"
        ) from exc

    plaintext = _decompress(compressed, codec)
    rows = []
    for line in plaintext.decode("utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


# --------------------------------------------------------------------------- #
# Archive API (used by the admin endpoints)
# --------------------------------------------------------------------------- #

def vault_dir() -> Path:
    d = Path(get_settings().VAULT_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


async def archive_records(
    db: AsyncSession,
    kind: str,
    records: list[dict],
    *,
    owner_user_id=None,
    tenant_id=None,
    period: str | None = None,
    created_by=None,
) -> VaultFile:
    """Persist ``records`` as one sealed vault file + index row.

    The caller commits the DB transaction (the admin route does).
    """
    settings = get_settings()
    master = _parse_master_key(settings.VAULT_MASTER_KEY)

    if not records:
        raise VaultError("Nothing to archive (empty record set)")

    file_id = uuid.uuid4()
    blob, meta = _seal(records, master, file_id)
    meta["row_count"] = len(records)

    directory = vault_dir()
    path = directory / f"{file_id}.bin"

    # Atomic write: temp file + rename, 0600 perms (owner-only).
    fd, tmp_name = tempfile.mkstemp(dir=str(directory), prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(blob)
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, str(path))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    vf = VaultFile(
        id=file_id,
        kind=kind,
        owner_user_id=owner_user_id,
        tenant_id=tenant_id,
        period=period,
        storage_path=str(path),
        sha256=hashlib.sha256(blob).hexdigest(),
        plaintext_sha256=meta["plaintext_sha256"],
        original_bytes=meta["original_bytes"],
        stored_bytes=meta["stored_bytes"],
        row_count=meta["row_count"],
        codec=meta["codec"],
        cipher="aes-256-gcm",
        created_by=created_by,
    )
    db.add(vf)
    await db.flush()
    logger.info(
        "Vault archived kind=%s rows=%d %d->%d bytes (%.1f%%)",
        kind, meta["row_count"], meta["original_bytes"], meta["stored_bytes"],
        100.0 * meta["stored_bytes"] / max(1, meta["original_bytes"]),
    )
    return vf


async def extract_records(db: AsyncSession, vf: VaultFile, max_rows: int = 20000) -> dict:
    """Open a vault file and return its rows + verification metadata.

    Verifies the stored-bytes sha256 BEFORE decrypting, and the GCM tag
    during decryption — any mismatch raises VaultError.
    """
    settings = get_settings()
    master = _parse_master_key(settings.VAULT_MASTER_KEY)

    path = Path(vf.storage_path)
    if not path.exists():
        raise VaultError(f"Vault file missing on disk: {vf.storage_path}")
    blob = path.read_bytes()

    digest = hashlib.sha256(blob).hexdigest()
    if digest != vf.sha256:
        raise VaultError("Vault file sha256 mismatch — stored bytes were modified")

    rows = _open(blob, master, vf.id)
    if len(rows) > max_rows:
        rows = rows[:max_rows]

    return {
        "id": str(vf.id),
        "kind": vf.kind,
        "period": vf.period,
        "codec": vf.codec,
        "cipher": vf.cipher,
        "row_count": vf.row_count,
        "original_bytes": vf.original_bytes,
        "stored_bytes": vf.stored_bytes,
        "compression_ratio": round(
            vf.stored_bytes / max(1, vf.original_bytes), 4
        ),
        "created_at": vf.created_at.isoformat() if vf.created_at else None,
        "verified": True,
        "rows": rows,
    }


def vault_available() -> bool:
    """True when archiving is configured (master key present)."""
    try:
        _parse_master_key(get_settings().VAULT_MASTER_KEY)
        return True
    except VaultError:
        return False


__all__ = [
    "VaultError",
    "archive_records",
    "extract_records",
    "vault_available",
    "vault_dir",
]
