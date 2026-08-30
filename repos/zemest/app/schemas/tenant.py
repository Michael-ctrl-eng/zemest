from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel
from datetime import datetime


class TenantCreate(BaseModel):
    page_name: str
    fb_page_id: str | None = None
    page_access_token: str | None = None
    website_url: str | None = None
    business_phone: str | None = None
    business_email: str | None = None
    notification_pref: str = "email"

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "page_name": "My Fashion Store",
                    "fb_page_id": "123456789",
                    "website_url": "https://myfashionstore.com",
                    "business_phone": "01012345678",
                    "notification_pref": "email",
                }
            ]
        }
    }


class TenantUpdate(BaseModel):
    page_name: str | None = None
    page_access_token: str | None = None
    fb_page_id: str | None = None
    website_url: str | None = None
    business_phone: str | None = None
    business_email: str | None = None
    notification_pref: str | None = None
    delivery_inside_cairo: Decimal | None = None
    delivery_outside_cairo: Decimal | None = None
    free_delivery_above: Decimal | None = None
    payment_methods: dict | None = None
    order_api_config: dict | None = None


class TenantResponse(BaseModel):
    id: str
    fb_page_id: str | None
    page_name: str
    website_url: str | None
    business_phone: str | None
    business_email: str | None
    notification_pref: str
    delivery_inside_cairo: Decimal | None = None
    delivery_outside_cairo: Decimal | None = None
    free_delivery_above: Decimal | None = None
    payment_methods: dict | None = None
    order_api_config: dict | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
