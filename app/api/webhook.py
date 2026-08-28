"""Webhook handlers for Facebook Messenger, Instagram DMs, and WhatsApp.

Handles all event types that Chatwoot handles:
- Messenger: message, message_echo, delivery, read, postback
- Instagram: message, read, story mentions, reels/posts
- WhatsApp: text, image, audio, interactive
"""
import hashlib
import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Request, Response
from sqlalchemy import select

from app.config import get_settings
from app.database import async_session
from app.models.tenant import Tenant
from app.utils.security import verify_fb_signature

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhook", tags=["Webhook"])


# =========================================================================
# Facebook Messenger
# =========================================================================

@router.get("/messenger")
async def verify_webhook(request: Request):
    """Facebook webhook verification challenge."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.FB_VERIFY_TOKEN:
        logger.info("Messenger webhook verified")
        return Response(content=challenge, media_type="text/plain")

    logger.warning("Messenger webhook verification failed")
    return Response(content="Forbidden", status_code=403)


@router.post("/messenger")
async def receive_messenger_event(
    request: Request, background_tasks: BackgroundTasks
):
    """Receive Messenger webhook events (message, delivery, read, postback, echo)."""
    body = await request.body()

    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_fb_signature(body, signature):
        return Response(content="Invalid signature", status_code=403)

    data = await request.json()

    if data.get("object") != "page":
        return Response(content="Not a page event", status_code=404)

    for entry in data.get("entry", []):
        page_id = entry.get("id")
        events = entry.get("messaging", []) or entry.get("standby", [])
        for event in events:
            event_type = _classify_messenger_event(event)

            if event_type == "message_echo":
                continue
            elif event_type == "delivery":
                background_tasks.add_task(_handle_delivery, page_id, event)
            elif event_type == "read":
                background_tasks.add_task(_handle_read_receipt, page_id, event)
            elif event_type == "postback":
                background_tasks.add_task(_handle_postback, page_id, event)
            elif event_type == "message":
                background_tasks.add_task(_process_messenger_message, page_id, event)

    return Response(content="EVENT_RECEIVED", status_code=200)


def _classify_messenger_event(event: dict) -> str:
    if "message" in event:
        message = event["message"]
        if message.get("is_echo"):
            return "message_echo"
        return "message"
    if "delivery" in event:
        return "delivery"
    if "read" in event:
        return "read"
    if "postback" in event:
        return "postback"
    if "referral" in event:
        return "referral"
    return "unknown"


async def _process_messenger_message(page_id: str, event: dict):
    sender_id = event.get("sender", {}).get("id")
    message = event.get("message", {})
    message_text = message.get("text", "")

    media_urls = []
    audio_urls = []
    for att in message.get("attachments", []):
        att_type = att.get("type", "")
        url = att.get("payload", {}).get("url", "")
        if att_type in ("image", "video", "file"):
            media_urls.append(url)
        elif att_type == "audio":
            audio_urls.append(url)

    if not sender_id:
        return
    if not message_text and not media_urls and not audio_urls:
        return

    if not message_text:
        if media_urls:
            message_text = "(image)"
        elif audio_urls:
            message_text = "(voice note)"

    try:
        async with async_session() as db:
            result = await db.execute(
                select(Tenant).where(Tenant.fb_page_id == page_id)
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                logger.warning(f"No tenant for page {page_id}")
                return

            from app.ai.agent import process_customer_message
            from app.services.messenger_service import (
                mark_seen, typing_on, typing_off, send_text_message,
            )

            await mark_seen(tenant.page_access_token, sender_id)
            await typing_on(tenant.page_access_token, sender_id)

            try:
                # If the sender is the page owner, route to owner_chat
                # instead of the customer-facing agent flow (MASTER_PROMPT §7).
                if tenant.owner_psid and sender_id == tenant.owner_psid:
                    reply = await _handle_owner_message(db, tenant, message_text)
                else:
                    reply = await process_customer_message(
                        db=db,
                        tenant=tenant,
                        sender_psid=sender_id,
                        message_text=message_text,
                        fb_message_id=message.get("mid"),
                        channel="messenger",
                        media_urls=media_urls,
                        audio_urls=audio_urls,
                    )
                # Don't send 'duplicate' replies to customers (Meta retry dedup)
                if reply and reply != "duplicate":
                    send_result = await send_text_message(tenant.page_access_token, sender_id, reply)
                    if send_result.get("_auth_error"):
                        logger.error(f"AUTH ERROR for page {page_id} - token may be expired/revoked")
                else:
                    logger.info(f"Skipping send for duplicate/empty reply on page {page_id}")

            finally:
                await typing_off(tenant.page_access_token, sender_id)

            await db.commit()

    except Exception as e:
        logger.error(f"Error processing Messenger message from {sender_id}: {e}", exc_info=True)


async def _handle_owner_message(db, tenant, message_text: str) -> str:
    """Process a message from the page owner (sender == tenant.owner_psid).

    Parses the natural-language instruction via owner_chat and executes the
    resulting action. Falls back to the customer agent flow on any error so
    the owner still receives a reply.
    """
    from app.services.owner_chat import (
        parse_owner_instruction,
        execute_owner_action,
        _track_usage,
    )

    try:
        # Pull a small product snapshot to ground the LLM parser
        from app.models.product import Product
        from sqlalchemy import select
        rows = await db.execute(
            select(Product)
            .where(Product.tenant_id == tenant.id, Product.is_active == True)
            .order_by(Product.created_at.desc())
            .limit(20)
        )
        products = [
            {"name": p.name, "price": float(p.price or 0)}
            for p in rows.scalars().all()
        ]

        action, token_info = await parse_owner_instruction(message_text, products)
        await _track_usage(db, tenant, token_info)

        if not action:
            return "مش فاهم طلبك ده. ممكن توضّح أكتر؟ 🙏"

        return await execute_owner_action(db, tenant, action)

    except Exception as e:
        logger.error(f"Owner chat handling failed: {e}", exc_info=True)
        return "حصل خطأ، جرّب تاني 🙏"


async def _handle_delivery(page_id: str, event: dict):
    delivery = event.get("delivery", {})
    mids = delivery.get("mids", [])
    watermark = delivery.get("watermark", 0)
    logger.debug(f"Delivery receipt for page {page_id}: {len(mids)} messages, watermark={watermark}")


async def _handle_read_receipt(page_id: str, event: dict):
    read = event.get("read", {})
    watermark = read.get("watermark", 0)
    logger.debug(f"Read receipt for page {page_id}: watermark={watermark}")


async def _handle_postback(page_id: str, event: dict):
    postback = event.get("postback", {})
    sender_id = event.get("sender", {}).get("id")
    payload = postback.get("payload", "")
    title = postback.get("title", "")

    logger.info(f"Postback from {sender_id} on page {page_id}: payload={payload}, title={title}")

    if not sender_id or not payload:
        return

    try:
        async with async_session() as db:
            result = await db.execute(
                select(Tenant).where(Tenant.fb_page_id == page_id)
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                return

            from app.ai.agent import process_customer_message
            from app.services.messenger_service import send_text_message

            reply = await process_customer_message(
                db=db,
                tenant=tenant,
                sender_psid=sender_id,
                message_text=title or payload,
                channel="messenger",
            )
            if reply and reply != "duplicate":
                await send_text_message(tenant.page_access_token, sender_id, reply)
            await db.commit()

    except Exception as e:
        logger.error(f"Error processing postback from {sender_id}: {e}", exc_info=True)


# =========================================================================
# Instagram DMs
# =========================================================================

@router.get("/instagram")
async def verify_instagram_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.FB_VERIFY_TOKEN:
        return Response(content=challenge, media_type="text_plain")
    return Response(content="Forbidden", status_code=403)


@router.post("/instagram")
async def receive_instagram_event(
    request: Request, background_tasks: BackgroundTasks
):
    body = await request.body()

    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_meta_signature(body, signature):
        return Response(content="Invalid signature", status_code=403)

    data = await request.json()

    for entry in data.get("entry", []):
        page_id = entry.get("id")
        events = entry.get("messaging", []) or entry.get("standby", [])

        for event in events:
            is_echo = event.get("message", {}).get("is_echo", False)
            if is_echo:
                continue

            event_type = _classify_instagram_event(event)

            if event_type == "message":
                background_tasks.add_task(_process_instagram_message, page_id, event)
            elif event_type == "read":
                background_tasks.add_task(_handle_ig_read, page_id, event)

    return Response(content="EVENT_RECEIVED", status_code=200)


def _classify_instagram_event(event: dict) -> str:
    if "message" in event:
        return "message"
    if "read" in event:
        return "read"
    if "reaction" in event:
        return "reaction"
    return "unknown"


async def _process_instagram_message(page_id: str, event: dict):
    sender_id = event.get("sender", {}).get("id")
    message = event.get("message", {})
    message_text = message.get("text", "")

    media_urls = []
    audio_urls = []
    for att in message.get("attachments", []):
        att_type = att.get("type", "")
        url = att.get("payload", {}).get("url", "")
        if att_type in ("image", "ig_reel", "ig_post"):
            media_urls.append(url)
        elif att_type == "audio":
            audio_urls.append(url)

    story_url = None
    reply_to = message.get("reply_to", {})
    if reply_to.get("story"):
        story_url = reply_to["story"].get("url")

    if not sender_id:
        return
    if not message_text and not media_urls and not audio_urls and not story_url:
        return

    if not message_text:
        if story_url:
            message_text = "(story reply)"
        elif media_urls:
            message_text = "(image)"
        elif audio_urls:
            message_text = "(voice note)"

    try:
        async with async_session() as db:
            result = await db.execute(
                select(Tenant).where(Tenant.ig_user_id == page_id)
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                result = await db.execute(
                    select(Tenant).where(Tenant.fb_page_id == page_id)
                )
                tenant = result.scalar_one_or_none()
            if not tenant:
                logger.warning(f"No tenant for Instagram {page_id}")
                return

            from app.ai.agent import process_customer_message
            from app.services.messenger_service import (
                mark_seen, typing_on, typing_off, send_text_message,
            )

            token = tenant.ig_access_token or tenant.page_access_token
            if not token:
                return

            await mark_seen(token, sender_id)
            await typing_on(token, sender_id)

            try:
                reply = await process_customer_message(
                    db=db,
                    tenant=tenant,
                    sender_psid=sender_id,
                    message_text=message_text,
                    fb_message_id=message.get("mid"),
                    channel="instagram",
                    media_urls=media_urls,
                    audio_urls=audio_urls,
                )
                # Don't send 'duplicate' replies (Meta retry dedup)
                if reply and reply != "duplicate":
                    await send_text_message(token, sender_id, reply)
            finally:
                await typing_off(token, sender_id)

            await db.commit()

    except Exception as e:
        logger.error(f"Error processing Instagram message from {sender_id}: {e}", exc_info=True)


async def _handle_ig_read(page_id: str, event: dict):
    read = event.get("read", {})
    watermark = read.get("watermark", 0)
    logger.debug(f"Instagram read receipt for {page_id}: watermark={watermark}")


# =========================================================================
# WhatsApp (via WhatsApp Business API)
# =========================================================================

@router.get("/whatsapp")
async def verify_whatsapp_webhook(request: Request):
    """WhatsApp webhook verification (same pattern as Messenger)."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.FB_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified")
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Forbidden", status_code=403)


@router.post("/whatsapp")
async def receive_whatsapp_event(
    request: Request, background_tasks: BackgroundTasks
):
    body = await request.body()

    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_meta_signature(body, signature):
        return Response(content="Invalid signature", status_code=403)

    data = await request.json()

    for entry in data.get("entry", []):
        phone_number_id = entry.get("id")
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            contacts = value.get("contacts", [])
            for msg in messages:
                background_tasks.add_task(
                    _process_whatsapp_message, phone_number_id, msg, contacts
                )

    return Response(content="EVENT_RECEIVED", status_code=200)


async def _process_whatsapp_message(phone_number_id: str, msg: dict, contacts: list):
    sender_id = msg.get("from", "")
    msg_type = msg.get("type", "")
    message_text = ""
    media_urls = []
    audio_urls = []

    if msg_type == "text":
        message_text = msg.get("text", {}).get("body", "")
    elif msg_type == "image":
        media_urls.append(msg.get("image", {}).get("id", ""))
    elif msg_type == "audio":
        audio_urls.append(msg.get("audio", {}).get("id", ""))
    elif msg_type == "video":
        media_urls.append(msg.get("video", {}).get("id", ""))
    elif msg_type == "document":
        media_urls.append(msg.get("document", {}).get("id", ""))
    elif msg_type == "interactive":
        interactive = msg.get("interactive", {})
        if interactive.get("type") == "button_reply":
            message_text = interactive.get("button_reply", {}).get("id", "")
        elif interactive.get("type") == "list_reply":
            message_text = interactive.get("list_reply", {}).get("id", "")

    if not sender_id:
        return
    if not message_text and not media_urls and not audio_urls:
        return

    customer_name = ""
    for c in contacts:
        if c.get("wa_id") == sender_id:
            customer_name = c.get("profile", {}).get("name", "")
            break

    try:
        async with async_session() as db:
            result = await db.execute(
                select(Tenant).where(Tenant.wa_phone_number_id == phone_number_id)
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                logger.warning(f"No tenant for WhatsApp number {phone_number_id}")
                return

            from app.ai.agent import process_customer_message
            from app.services.whatsapp_service import send_whatsapp_message

            reply = await process_customer_message(
                db=db,
                tenant=tenant,
                sender_psid=sender_id,
                message_text=message_text,
                fb_message_id=msg.get("id"),
                customer_name=customer_name,
                channel="whatsapp",
                media_urls=media_urls,
                audio_urls=audio_urls,
            )

            # Don't send 'duplicate' replies (Meta retry dedup)
            if reply and reply != "duplicate":
                await send_whatsapp_message(tenant, sender_id, reply)
            await db.commit()

    except Exception as e:
        logger.error(f"Error processing WhatsApp message from {sender_id}: {e}", exc_info=True)


# =========================================================================
# Signature verification
# =========================================================================

def _verify_meta_signature(body: bytes, signature: str) -> bool:
    """Verify X-Hub-Signature-256 for Facebook/Instagram/WhatsApp webhooks.

    Fails CLOSED: returns False when FB_APP_SECRET is missing or empty.
    This is the security-critical posture — never accept unsigned traffic.
    """
    if not signature:
        return False

    secret = settings.FB_APP_SECRET
    if not secret:
        logger.error("FB_APP_SECRET not set — rejecting webhook (fail-closed)")
        return False

    expected = hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
