import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Index, String, Text, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("idx_orders_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"))
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("conversations.id"))
    order_number: Mapped[str] = mapped_column(String(20), unique=True)
    customer_name: Mapped[str] = mapped_column(String(255))
    customer_phone: Mapped[str] = mapped_column(String(20))
    governorate: Mapped[str] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(100))
    area: Mapped[Optional[str]] = mapped_column(String(100))
    address_detail: Mapped[str] = mapped_column(Text)
    payment_method: Mapped[str] = mapped_column(String(30), default="cod")
    payment_phone_last2: Mapped[Optional[str]] = mapped_column(String(10))
    payment_trx_id: Mapped[Optional[str]] = mapped_column(String(50))
    # External API call tracking
    api_status: Mapped[Optional[str]] = mapped_column(String(20))  # success, failed, pending, not_configured
    api_response: Mapped[Optional[str]] = mapped_column(Text)  # raw response body
    api_status_code: Mapped[Optional[int]] = mapped_column(Integer)
    api_called_at: Mapped[Optional[datetime]] = mapped_column()
    api_external_id: Mapped[Optional[str]] = mapped_column(String(100))  # order ID from their system
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    delivery_charge: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    tenant = relationship("Tenant", back_populates="orders")
    customer = relationship("Customer", back_populates="orders")
    conversation = relationship("Conversation", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("products.id"))
    product_name: Mapped[str] = mapped_column(String(500))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    order = relationship("Order", back_populates="items")
