import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_tenant
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.message import Message
from app.schemas.conversation import (
    ConversationListResponse,
    ConversationResponse,
    ConversationSummaryResponse,
    MessageResponse,
)

router = APIRouter(prefix="/api/tenants/{tenant_id}/conversations", tags=["Conversations"])


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    total = await db.scalar(
        select(func.count(Conversation.id)).where(
            Conversation.tenant_id == tenant.id
        )
    ) or 0

    result = await db.execute(
        select(Conversation)
        .where(Conversation.tenant_id == tenant.id)
        .options(selectinload(Conversation.customer))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .order_by(Conversation.last_message_at.desc())
    )
    conversations = result.scalars().all()

    # Audit B8: the list must NOT ship full message threads (the dashboard
    # polls it every 10 s). Fetch just the preview + count for THIS page's
    # conversations — two bounded queries instead of N lazy loads.
    conv_ids = [c.id for c in conversations]
    last_messages: dict = {}
    message_counts: dict = {}
    if conv_ids:
        # Count per conversation.
        count_rows = await db.execute(
            select(
                Message.conversation_id,
                func.count(Message.id),
            )
            .where(Message.conversation_id.in_(conv_ids))
            .group_by(Message.conversation_id)
        )
        message_counts = {row[0]: row[1] for row in count_rows}

        # Last message per conversation: max(created_at) per conversation
        # joined back to its content (portable: no window functions).
        max_sub = (
            select(
                Message.conversation_id.label("cid"),
                func.max(Message.created_at).label("max_created"),
            )
            .where(Message.conversation_id.in_(conv_ids))
            .group_by(Message.conversation_id)
            .subquery()
        )
        last_rows = await db.execute(
            select(Message.conversation_id, Message.content)
            .join(
                max_sub,
                and_(
                    Message.conversation_id == max_sub.c.cid,
                    Message.created_at == max_sub.c.max_created,
                ),
            )
            .where(Message.conversation_id.in_(conv_ids))
        )
        last_messages = {row[0]: row[1] for row in last_rows}

    return ConversationListResponse(
        conversations=[
            ConversationSummaryResponse(
                id=str(c.id),
                customer_name=c.customer.name if c.customer else None,
                status=c.status,
                started_at=c.started_at,
                last_message_at=c.last_message_at,
                last_message_preview=(last_messages.get(c.id) or "")[:80],
                message_count=message_counts.get(c.id, 0),
            )
            for c in conversations
        ],
        total=total,
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant.id,
        )
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.customer),
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationResponse(
        id=str(conv.id),
        customer_name=conv.customer.name if conv.customer else None,
        status=conv.status,
        started_at=conv.started_at,
        last_message_at=conv.last_message_at,
        messages=[
            MessageResponse(
                id=str(m.id),
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in conv.messages
        ],
    )
