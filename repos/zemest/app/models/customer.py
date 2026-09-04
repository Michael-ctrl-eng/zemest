import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.db_types import EncryptedText


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "fb_psid", name="uq_customer_psid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    fb_psid: Mapped[str] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(20), default="messenger")  # messenger|instagram|whatsapp
    name: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    # Egyptian address fields
    governorate: Mapped[Optional[str]] = mapped_column(String(100))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    area: Mapped[Optional[str]] = mapped_column(String(100))
    address_detail: Mapped[Optional[str]] = mapped_column(Text)
    # Optional buyer demographics (PII — encrypted at rest). ISO date string;
    # surfaced (with computed age) in the admin analytics customer views.
    date_of_birth: Mapped[Optional[str]] = mapped_column(EncryptedText(), default=None)
    # Public profile link when derivable (wa.me/<phone> for WhatsApp,
    # instagram.com/<username> for IG) or set by an admin.
    profile_url: Mapped[Optional[str]] = mapped_column(String(512), default=None)

    # --- Buyer intelligence (auto-enriched from chats; see
    #     app/ai/enrichment.py — zero-cost extraction, no LLM call) ---
    email: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    # Accumulated interest tags: ["shoes", "discounts", "delivery"] ...
    interests: Mapped[Optional[list]] = mapped_column(JSON, default=None)
    # Country inferred from phone/address when available.
    country: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    tenant = relationship("Tenant", back_populates="customers")
    conversations = relationship("Conversation", back_populates="customer")
    orders = relationship("Order", back_populates="customer")
