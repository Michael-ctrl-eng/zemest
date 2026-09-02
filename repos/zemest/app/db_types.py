"""SQLAlchemy column type encrypting values at rest (audit A4-H4).

``EncryptedText`` behaves exactly like ``Text`` in Python (plain str in,
plain str out) but stores Fernet ciphertext in the database. Legacy
plaintext rows pass through unchanged on read — see
:mod:`app.utils.token_crypto`.
"""
from __future__ import annotations

from sqlalchemy import Text, TypeDecorator

from app.utils.token_crypto import decrypt_token, encrypt_token


class EncryptedText(TypeDecorator):
    """Transparently encrypted Text column.

    Usage:
        page_access_token: Mapped[Optional[str]] = mapped_column(EncryptedText())
    """

    impl = Text
    cache_ok = True  # the type is stable — plaintext↔ciphertext never changes SQL shape

    def process_bind_param(self, value, dialect):
        # WRITE path: encrypt.
        return encrypt_token(value)

    def process_result_value(self, value, dialect):
        # READ path: decrypt (legacy plaintext passthrough).
        return decrypt_token(value)


__all__ = ["EncryptedText"]
