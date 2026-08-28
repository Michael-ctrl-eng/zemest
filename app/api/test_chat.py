import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.tenant import Tenant
from app.schemas.webhook import TestChatRequest, TestChatResponse
from sqlalchemy import select

router = APIRouter(prefix="/api/test", tags=["Testing"])


@router.post("/chat", response_model=TestChatResponse)
async def test_chat(
    req: TestChatRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Simulate a customer message for local testing without Facebook.

    This endpoint mimics the Messenger webhook flow but works locally.
    Use it to test the AI sales agent without connecting to Facebook.
    """
    result = await db.execute(
        select(Tenant).where(
            Tenant.id == uuid.UUID(req.tenant_id),
            Tenant.owner_id == user.id,
        )
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Use a test PSID
    test_psid = f"test_{user.id}"

    from app.ai.agent import process_customer_message

    reply = await process_customer_message(
        db=db,
        tenant=tenant,
        sender_psid=test_psid,
        message_text=req.message,
        customer_name=req.customer_name,
    )

    # Get conversation and customer IDs for response
    from app.models.customer import Customer
    from app.models.conversation import Conversation

    cust_result = await db.execute(
        select(Customer).where(
            Customer.tenant_id == tenant.id,
            Customer.fb_psid == test_psid,
        )
    )
    customer = cust_result.scalar_one_or_none()

    conversation = None
    if customer:
        conv_result = await db.execute(
            select(Conversation)
            .where(
                Conversation.tenant_id == tenant.id,
                Conversation.customer_id == customer.id,
            )
            .order_by(Conversation.last_message_at.desc())
            .limit(1)
        )
        conversation = conv_result.scalar_one_or_none()

    # Get token usage for this response
    tokens_used = 0
    try:
        from app.models.token_usage import TokenUsage
        from sqlalchemy import desc
        usage_result = await db.execute(
            select(TokenUsage)
            .where(TokenUsage.tenant_id == tenant.id)
            .order_by(desc(TokenUsage.created_at))
            .limit(1)
        )
        last_usage = usage_result.scalar_one_or_none()
        if last_usage:
            tokens_used = last_usage.total_tokens
    except Exception:
        pass

    return TestChatResponse(
        reply=reply,
        conversation_id=str(conversation.id) if conversation else "",
        customer_id=str(customer.id) if customer else "",
        tokens_used=tokens_used,
    )


@router.post("/postiz-chat")
async def postiz_chat(
    req: TestChatRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Chat with the Postiz AI agent for social media scheduling.

    This endpoint handles requests like:
    - "write a post about X"
    - "schedule a post"
    - "what's my best time to post?"
    - "show my insights"
    - "list my scheduled posts"

    It delegates to Postiz AI when available, falling back to our own LLM.
    """
    result = await db.execute(
        select(Tenant).where(
            Tenant.id == uuid.UUID(req.tenant_id),
            Tenant.owner_id == user.id,
        )
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Tenant not found")

    from app.ai.postiz_chat import handle_postiz_chat_request

    result = await handle_postiz_chat_request(
        tenant=tenant,
        user_message=req.message,
        user_id=str(user.id),
    )

    return {
        "reply": result.get("reply", ""),
        "action": result.get("action", "unknown"),
        "data": result.get("data", {}),
    }
