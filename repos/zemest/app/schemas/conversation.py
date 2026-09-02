from __future__ import annotations

from pydantic import BaseModel
from datetime import datetime


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: str
    customer_name: str | None = None
    status: str
    started_at: datetime
    last_message_at: datetime
    messages: list[MessageResponse] = []

    model_config = {"from_attributes": True}


class ConversationSummaryResponse(BaseModel):
    """List item — deliberately message-free.

    Audit B8: the list response used to embed every conversation's full
    message thread; the dashboard polls the list every 10s, so the payload
    grew with chat history. ``last_message_preview`` + ``message_count``
    give the list UI everything it renders.
    """

    id: str
    customer_name: str | None = None
    status: str
    started_at: datetime
    last_message_at: datetime
    last_message_preview: str = ""
    message_count: int = 0

    model_config = {"from_attributes": True}


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummaryResponse]
    total: int
