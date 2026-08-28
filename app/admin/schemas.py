"""Pydantic schemas for the admin REST API."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BlockUserRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="Reason for blocking")


class IPBanCreate(BaseModel):
    ip_or_cidr: str = Field(..., description="Single IP or CIDR range, e.g. 203.0.113.5 or 203.0.113.0/24")
    reason: Optional[str] = None


class IPBanResponse(BaseModel):
    id: uuid.UUID
    ip_or_cidr: str
    reason: Optional[str]
    banned_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class SiteUserBlockResponse(BaseModel):
    user_id: uuid.UUID
    is_blocked: bool
    blocked_reason: Optional[str]
    blocked_at: Optional[datetime]

    model_config = {"from_attributes": True}


class UserSessionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    ip_address: str
    country: Optional[str]
    country_code: Optional[str]
    city: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    user_agent: Optional[str]
    device_type: Optional[str]
    login_at: datetime
    logout_at: Optional[datetime]
    last_activity: datetime
    is_active: bool

    model_config = {"from_attributes": True}


class AuditLogResponse(BaseModel):
    id: int
    admin_id: uuid.UUID
    action: str
    target_type: Optional[str]
    target_id: Optional[str]
    metadata_: Optional[dict]
    ip: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedAuditLog(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


class ActiveUsersResponse(BaseModel):
    active_count: int
    sampled_at: datetime


class GeoDistributionEntry(BaseModel):
    country: Optional[str]
    country_code: Optional[str]
    user_count: int


class GeoDistributionResponse(BaseModel):
    distribution: list[GeoDistributionEntry]
    total: int


__all__ = [
    "BlockUserRequest",
    "IPBanCreate",
    "IPBanResponse",
    "SiteUserBlockResponse",
    "UserSessionResponse",
    "AuditLogResponse",
    "PaginatedAuditLog",
    "ActiveUsersResponse",
    "GeoDistributionEntry",
    "GeoDistributionResponse",
]
