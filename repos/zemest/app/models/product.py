import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import JSON, ForeignKey, Index, String, Text, Boolean, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source", "source_ref", name="uq_product_source"),
        Index("idx_products_tenant_active", "tenant_id", "is_active"),
    )

    # === Fixed columns (universal for any product) ===
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(500))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")
    source_ref: Mapped[Optional[str]] = mapped_column(String(512))

    # === Flexible attributes (any key-value pairs the business needs) ===
    # Examples: {"color": "red", "size": "XL", "weight": "500g", "flavor": "chocolate",
    #            "brand": "Samsung", "RAM": "8GB", "category": "Electronics",
    #            "description": "...", "sku": "ABC-123", "stock_status": "in_stock",
    #            "image_url": "https://...", "discount_price": 1200, "name_ar": "اسم عربي"}
    attributes: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    tenant = relationship("Tenant", back_populates="products")

    def to_dict(self) -> dict:
        """Flatten product into a single dict with all attributes."""
        data = {
            "id": str(self.id),
            "name": self.name,
            "price": float(self.price),
            "is_active": self.is_active,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if self.attributes:
            data.update(self.attributes)
        return data
