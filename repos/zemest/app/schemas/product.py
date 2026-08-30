from __future__ import annotations

from decimal import Decimal
from typing import Any
from pydantic import BaseModel
from datetime import datetime


class ProductCreate(BaseModel):
    """Create a product with any attributes.

    Only `name` and `price` are required. Everything else is stored as
    flexible attributes — the system adapts to any product format.

    Examples:
        Clothing: {"name": "Cotton Galabiya", "price": 500, "color": "white", "size": "free", "material": "cotton"}
        Electronics: {"name": "Samsung A15", "price": 8000, "brand": "Samsung", "RAM": "6GB", "storage": "128GB"}
        Food: {"name": "Koshari Tray", "price": 120, "weight": "1kg", "fresh": true}
        Any format: {"name": "...", "price": ..., ...any other fields...}
    """
    name: str
    price: Decimal

    model_config = {
        "extra": "allow",
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Cotton Galabiya",
                    "price": "850.00",
                    "name_ar": "جلابية قطن مصري",
                    "description": "Traditional Egyptian cotton galabiya",
                    "category": "Clothing",
                    "color": "white & gold",
                    "material": "cotton",
                    "stock_status": "in_stock",
                },
                {
                    "name": "Samsung Galaxy A15",
                    "price": "8000.00",
                    "brand": "Samsung",
                    "RAM": "6GB",
                    "storage": "128GB",
                    "color": "Blue",
                    "warranty": "1 year",
                },
                {
                    "name": "Chocolate Cake",
                    "price": "450.00",
                    "flavor": "dark chocolate",
                    "weight": "1kg",
                    "serves": "8-10 people",
                    "eggless": False,
                },
            ]
        },
    }


class ProductUpdate(BaseModel):
    """Update any fields. Only provided fields are changed."""
    name: str | None = None
    price: Decimal | None = None
    is_active: bool | None = None

    model_config = {"extra": "allow"}


class ProductResponse(BaseModel):
    """Flattened product — fixed fields + all custom attributes at top level."""
    id: str
    name: str
    price: Decimal
    is_active: bool
    source: str
    created_at: datetime
    attributes: dict[str, Any] = {}

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    products: list[ProductResponse]
    total: int
    page: int
    page_size: int
