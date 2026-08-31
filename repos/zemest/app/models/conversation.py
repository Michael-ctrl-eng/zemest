import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, DateTime, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="messenger")  # messenger|instagram|whatsapp
    status: Mapped[str] = mapped_column(String(20), default="active")
    started_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    last_message_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())

    # --- Silent trainer: junk (friend chat) vs work (commerce) classification.
    # Written automatically by app.ai.silent_trainer — never by the user. ---
    classification: Mapped[Optional[str]] = mapped_column(String(20), default=None)  # commerce|junk|mixed
    classification_score: Mapped[Optional[float]] = mapped_column(Float, default=None)
    classification_signals: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    classified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    classified_by: Mapped[Optional[str]] = mapped_column(String(16), default=None)

    tenant = relationship("Tenant", back_populates="conversations")
    customer = relationship("Customer", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")
    orders = relationship("Order", back_populates="conversation")
