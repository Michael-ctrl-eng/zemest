"""Refresh-token rotation ledger.

Refresh tokens are rotated on every use (OAuth 2.0 BCP): each refresh token
carries a unique ``jti`` and is recorded here. When a token is exchanged for
a new pair, its record is atomically flipped to ``revoked`` (compare-and-swap
via ``UPDATE ... WHERE revoked = false``). If an already-revoked ``jti`` is
presented again, that is token REUSE — proof the token was stolen and replayed
— and every token belonging to that user is revoked immediately.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RefreshTokenRecord(Base):
    __tablename__ = "refresh_token_records"

    #: JWT ID claim — primary key, one row per issued refresh token.
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)

    #: Owning user — indexed so the nuke-all-tokens path stays O(log n).
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    #: Flipped to True exactly once, inside the CAS update during rotation.
    #: Never flipped back — rotation is strictly forward.
    revoked: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", index=True
    )

    #: ``jti`` of the successor token issued in exchange for this one.
    #: A replayed token's successor chain is revocable in one query.
    replaced_by: Mapped[Optional[str]] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(index=True)

    user = relationship("User", back_populates="refresh_token_records")
