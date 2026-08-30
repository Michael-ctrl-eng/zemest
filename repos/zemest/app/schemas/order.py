from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel
from datetime import datetime


class OrderItemResponse(BaseModel):
    id: str
    product_name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: str
    order_number: str
    customer_name: str
    customer_phone: str
    governorate: str
    city: str
    area: str | None
    address_detail: str
    payment_method: str
    payment_phone_last2: str | None = None
    payment_trx_id: str | None = None
    api_status: str | None = None
    api_status_code: int | None = None
    api_external_id: str | None = None
    api_response: str | None = None
    api_called_at: str | None = None
    subtotal: Decimal
    delivery_charge: Decimal
    total: Decimal
    status: str
    notes: str | None
    created_at: datetime
    items: list[OrderItemResponse] = []

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    orders: list[OrderResponse]
    total: int
    page: int
    page_size: int


class OrderStatusUpdate(BaseModel):
    status: str
    notes: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [{"status": "confirmed"}]
        }
    }


class ManualOrderItemCreate(BaseModel):
    product_name: str
    quantity: int = 1
    unit_price: Decimal


class ManualOrderCreate(BaseModel):
    customer_name: str
    customer_phone: str
    governorate: str
    city: str
    area: str | None = None
    address_detail: str
    payment_method: str = "cod"
    delivery_charge: Decimal = Decimal("0")
    notes: str | None = None
    items: list[ManualOrderItemCreate]


class OrderNotesUpdate(BaseModel):
    notes: str
