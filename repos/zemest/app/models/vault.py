"""Encrypted data vault index.

One row per sealed archive on disk. The file at ``storage_path`` is laid
out as::

    b"ZV1" | codec-byte | 12-byte nonce | AES-256-GCM(ciphertext || tag)

where the plaintext is JSONL compressed with zstd (when installed) or
gzip level 9. The per-file key is HKDF-SHA256(VAULT_MASTER_KEY, salt =
file id bytes) — every file has an independent key, so a single leaked
archive key compromises nothing else.

``sha256`` covers the stored bytes (integrity), ``plaintext_sha256`` the
original JSONL (verification). Extraction (decrypt + decompress) is
exposed ONLY to superadmins and is audit-logged. See
app/services/vault.py.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VaultFile(Base):
    __tablename__ = "vault_files"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # user_profiles | customer_profiles | chat_archive | analytics
    kind: Mapped[str] = mapped_column(String(32), index=True)
    owner_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(default=None, index=True)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(default=None, index=True)
    period: Mapped[Optional[str]] = mapped_column(String(16), default=None)  # YYYY-MM or "all"
    storage_path: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    plaintext_sha256: Mapped[str] = mapped_column(String(64))
    original_bytes: Mapped[int] = mapped_column(Integer, default=0)
    stored_bytes: Mapped[int] = mapped_column(Integer, default=0)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    codec: Mapped[str] = mapped_column(String(8), default="gzip")  # zstd|gzip
    cipher: Mapped[str] = mapped_column(String(16), default="aes-256-gcm")
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow(), index=True)
