from __future__ import annotations

import uuid as _uuid

from pydantic import BaseModel, Field, field_validator


class TestChatRequest(BaseModel):
    """Simulate a customer message for local testing without Facebook."""

    # Typed as UUID: malformed values now fail Pydantic validation (422)
    # instead of raising ValueError inside the handler (500 + traceback).
    tenant_id: _uuid.UUID
    customer_name: str = "Test Customer"
    # min_length blocks whitespace/empty bodies that used to run the whole
    # pipeline, get rejected by the LLM provider, and persist an English
    # fallback apology into an Arabic conversation. max_length bounds
    # prompt size and latency (10KB used to cost 10.7k tokens / 5.5s).
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def _strip_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be empty or whitespace-only")
        return v

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
