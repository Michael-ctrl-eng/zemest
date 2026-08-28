from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CustomerResponse(BaseModel):
    id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    governorate: Optional[str] = None
    city: Optional[str] = None
    area: Optional[str] = None
    address_detail: Optional[str] = None
    created_at: datetime
    orders_count: int = 0
    conversations_count: int = 0
    total_spent: float = 0

    model_config = {"from_attributes": True}


class CustomerListResponse(BaseModel):
    customers: list[CustomerResponse]
    total: int
    page: int
    page_size: int


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    governorate: Optional[str] = None
    city: Optional[str] = None
    area: Optional[str] = None
    address_detail: Optional[str] = None
