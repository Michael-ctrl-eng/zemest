import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, Boolean, Numeric, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # --- Page connections (multi-channel per page) ---
    fb_page_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True)
    page_name: Mapped[str] = mapped_column(String(255))
    page_access_token: Mapped[Optional[str]] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    # Page owner's own Messenger PSID — messages from this sender bypass the
    # customer-agent flow and are routed to owner_chat (see MASTER_PROMPT §7).
    owner_psid: Mapped[Optional[str]] = mapped_column(String(64), index=True)

    # Instagram
    ig_user_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    ig_access_token: Mapped[Optional[str]] = mapped_column(Text)

    # WhatsApp (via WhatsApp Business API or WAHA)
    wa_phone_number_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    wa_access_token: Mapped[Optional[str]] = mapped_column(Text)
    wa_waba_id: Mapped[Optional[str]] = mapped_column(String(64))

    # --- Channel connection metadata (account display info + connect time) ---
    messenger_meta: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    instagram_meta: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    whatsapp_meta: Mapped[Optional[dict]] = mapped_column(JSON, default=None)

    # --- Calendar subscription (ICS feed auth token) ---
    calendar_token: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True)

    # --- Business info ---
    website_url: Mapped[Optional[str]] = mapped_column(String(512))
    business_phone: Mapped[Optional[str]] = mapped_column(String(20))
    business_email: Mapped[Optional[str]] = mapped_column(String(255))
    notification_pref: Mapped[str] = mapped_column(String(20), default="email")

    # --- Egyptian shipping ---
    delivery_inside_cairo: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), default=35)
    delivery_outside_cairo: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), default=60)
    free_delivery_above: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    # --- Payment methods (Egyptian) ---
    # {"vodafone_cash": "010...", "instapay": "010...", "fawry": "merchant_code"}
    payment_methods: Mapped[Optional[dict]] = mapped_column(JSON, default=None)

    # --- Per-page personality (auto-built from conversation history) ---
    style_profile: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    knowledge_base: Mapped[Optional[list]] = mapped_column(JSON, default=None)
    knowledge_built_at: Mapped[Optional[datetime]] = mapped_column(default=None)

    # --- Silent trainer checkpoint (epochs, maturity, error backoff,
    # resume state). Written only by the background trainer. ---
    training_state: Mapped[Optional[dict]] = mapped_column(JSON, default=None)

    # --- External order API config ---
    order_api_config: Mapped[Optional[dict]] = mapped_column(JSON, default=None)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    owner = relationship("User", back_populates="tenants")
    products = relationship("Product", back_populates="tenant", cascade="all, delete-orphan")
    customers = relationship("Customer", back_populates="tenant", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="tenant", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="tenant", cascade="all, delete-orphan")
    crawl_jobs = relationship("CrawlJob", back_populates="tenant", cascade="all, delete-orphan")
    knowledge_base_rel = relationship("KnowledgeBase", back_populates="tenant", uselist=False)
