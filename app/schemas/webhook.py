from __future__ import annotations

from pydantic import BaseModel


class TestChatRequest(BaseModel):
    """Simulate a customer message for local testing without Facebook."""

    tenant_id: str
    customer_name: str = "Test Customer"
    message: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tenant_id": "your-tenant-uuid",
                    "customer_name": "Karim",
                    "message": "إيه المنتجات اللي عندكم؟",
                }
            ]
        }
    }


class TestChatResponse(BaseModel):
    reply: str
    conversation_id: str
    customer_id: str
    tokens_used: int = 0


class CrawlRequest(BaseModel):
    url: str
    depth: int = 3

    model_config = {
        "json_schema_extra": {
            "examples": [{"url": "https://example-shop.com", "depth": 3}]
        }
    }


class CrawlJobResponse(BaseModel):
    id: str
    url: str
    status: str
    pages_found: int
    products_extracted: int
    error_message: str | None
    created_at: str

    model_config = {"from_attributes": True}
