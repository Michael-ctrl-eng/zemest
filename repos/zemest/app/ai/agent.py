from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.language_engine import detect_language_advanced
from app.ai.llm_client import chat_completion_with_usage
from app.ai.order_collector import clean_response_for_customer, extract_order_from_response
from app.ai.prompts import get_system_prompt
from app.knowledge.retriever import retrieve_context
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.message import Message
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 10

# Hard ceiling for the whole LLM ladder — a hung upstream must never pin the
# single event loop (measured worst case before this fix: ~3 minutes).
LLM_TOTAL_TIMEOUT_SECONDS = 45


async def process_customer_message(
    db: AsyncSession,
    tenant: Tenant,
    sender_psid: str,
    message_text: str,
    fb_message_id: str | None = None,
    customer_name: str | None = None,
    channel: str = "messenger",
    media_urls: list[str] | None = None,
    audio_urls: list[str] | None = None,
) -> str:
    """Process a customer message and return the AI response.

    channel: 'messenger' | 'instagram' | 'whatsapp'
    media_urls: image/video URLs from the message
    audio_urls: voice note URLs to transcribe
    """

    # 0. Transcribe voice notes if present
    if audio_urls:
        transcribed = await _transcribe_audio(audio_urls)
        if transcribed:
            message_text = transcribed

    # 0.5. Analyze product images if present
    vision_results = []
    if media_urls:
        vision_results = await _analyze_images(db, tenant, media_urls)
        if vision_results and not message_text.strip():
            # Customer sent only an image — ask what they need
            names = ", ".join(v.product_name for v in vision_results if v.product_name)
            message_text = f"إيه المنتج ده؟ {names}" if names else "عايز أعرف عن المنتج ده"

    # 1. Get or create customer
    customer = await _get_or_create_customer(
        db, tenant.id, sender_psid, customer_name, channel
    )

    # 1.5. Dedup by fb_message_id (Meta retries → same message N times).
    # Fast pre-check kept for the common case; the UNIQUE constraint on
    # messages.fb_message_id is the actual source of truth — a concurrent
    # duplicate insert now surfaces as IntegrityError on flush instead of
    # double-processing (double LLM spend, duplicate orders).
    if fb_message_id:
        existing = await db.execute(
            select(Message).where(Message.fb_message_id == fb_message_id)
        )
        if existing.scalar_one_or_none():
            logger.info(f"Duplicate message {fb_message_id} — skipping")
            return "duplicate"

    # 2. Get or create active conversation
    conversation = await _get_or_create_conversation(db, tenant.id, customer.id, channel)

    # 3. Save customer message. Eagerly flush here so a webhook duplicate
    # (the unique constraint on messages.fb_message_id) fails NOW — before
    # the expensive LLM call — instead of at the caller's commit after the
    # spend already happened.
    customer_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role="customer",
        content=message_text,
        fb_message_id=fb_message_id,
        channel=channel,
        media_urls=media_urls or [],
    )
    db.add(customer_msg)
    if fb_message_id:
        from sqlalchemy.exc import IntegrityError

        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            logger.info(f"Duplicate message {fb_message_id} (constraint race) — skipping")
            return "duplicate"

    # 4. Load conversation history
    history = await _load_conversation_history(db, conversation.id)

    # 5. Retrieve relevant products + knowledge
    products_context, knowledge_context = await retrieve_context(
        db, tenant.id, message_text, max_nodes=3
    )

    # 6. Detect language + dialect (multi-dialect engine)
    detection = detect_language_advanced(message_text)
    # Backward-compat: legacy 3-class label ("arabic"/"arabizi"/"english")
    # used by the fallback-response selector below.
    lang = detection.legacy_label

    # If the customer wrote in Arabizi, transliterate to Arabic so the LLM
    # understands the message better (LLMs handle Arabic script far better
    # than Latin Arabizi).
    user_message_for_llm = message_text
    if detection.primary_language == "arabizi" and detection.normalized_text:
        user_message_for_llm = detection.normalized_text
        logger.debug(
            f"Arabizi → Arabic transliteration: {message_text!r} → "
            f"{user_message_for_llm!r}"
        )

    # Choose the system-prompt dialect. If the customer wrote in English,
    # respond in English. Otherwise use the detected Arabic dialect
    # (defaulting to Egyptian when detection is unsure).
    if detection.primary_language == "english":
        prompt_dialect = "english"
    elif detection.arabic_dialect:
        prompt_dialect = detection.arabic_dialect
    else:
        prompt_dialect = "egyptian"

    # 7. Build system prompt with tenant settings + per-page personality
    style_profile = tenant.style_profile or {}
    system_prompt = get_system_prompt(
        business_name=tenant.page_name,
        products_context=products_context,
        knowledge_context=knowledge_context,
        language_hint=lang,
        delivery_inside_cairo=float(tenant.delivery_inside_cairo or 35),
        delivery_outside_cairo=float(tenant.delivery_outside_cairo or 60),
        free_delivery_above=float(tenant.free_delivery_above) if tenant.free_delivery_above else None,
        payment_methods=tenant.payment_methods,
        style_profile=style_profile,
        dialect=prompt_dialect,
    )

    # 8. Build messages for LLM
    #
    # Audit A5-H2: the injection detector + input delimiters existed but
    # were NEVER wired into the live path — customer text went into the
    # prompt verbatim. Now every user turn is delimited as DATA, and a
    # strong injection attempt is logged (chat continues, but the attempt
    # is visible + the turn is marked untrusted in the prompt itself).
    from app.middleware.prompt_injection import detect_prompt_injection, sanitize_user_input

    is_injection, _matched = detect_prompt_injection(message_text)
    if is_injection:
        logger.warning(
            "Prompt-injection attempt from PSID %s (tenant %s): %.80s",
            sender_psid, tenant.id, message_text,
        )

    llm_messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        role = "user" if msg.role == "customer" else "assistant"
        # History turns are customer-derived too — delimit them the same way.
        if msg.role == "customer":
            llm_messages.append({"role": role, "content": sanitize_user_input(msg.content)})
        else:
            llm_messages.append({"role": role, "content": msg.content})

    # Add image context if present.
    # NOTE: we use ``user_message_for_llm`` (which is the Arabizi→Arabic
    # transliteration when applicable) so the LLM receives clean Arabic
    # script rather than lossy Latin Arabizi.
    user_content = sanitize_user_input(user_message_for_llm)
    if media_urls:
        if vision_results:
            vision_text = "\n".join(
                f"- صورة: {v.product_name} ({v.category}) {v.color} — {v.details}"
                for v in vision_results if v.product_name
            )
            user_content += f"\n\n[العميل بعت صور. تحليل الصور:]\n{vision_text}"
        else:
            user_content += f"\n\n[العميل بعت صور: {', '.join(media_urls[:3])}]"

    llm_messages.append({"role": "user", "content": user_content})

    # 9. Call LLM (bounded: a slow/hung provider degrades to fallback instead
    #    of blocking the single worker for minutes).
    token_info = None
    llm_ok = False
    try:
        llm_result = await asyncio.wait_for(
            chat_completion_with_usage(llm_messages),
            timeout=LLM_TOTAL_TIMEOUT_SECONDS,
        )
        raw_response = llm_result.content
        token_info = llm_result
        llm_ok = bool(raw_response and raw_response.strip())
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raw_response = _get_fallback_response(lang)

    # 10. Check for order data in response
    order_data = extract_order_from_response(raw_response)
    order_created = False
    if order_data:
        order_created = await _create_order_from_data(db, tenant, customer, conversation, order_data)
        if order_created:
            conversation.status = "order_placed"
        else:
            # Order creation failed — override reply so we don't lie to customer
            raw_response = (
                "حصل خطأ في تسجيل الطلب، ممكن تجرب تاني؟ 🙏 "
                "لو المشكلة استمرت، ابعتلنا رسالة صوتية أو صورة."
            )

    # 11. Clean response
    clean_reply = clean_response_for_customer(raw_response)

    # 12. Save assistant message. Fallback apologies (LLM unavailable) are
    # persisted with is_fallback=True so BOTH style pipelines skip them —
    # otherwise the silent trainer literally learns its own failure text.
    assistant_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role="assistant",
        content=clean_reply,
        channel=channel,
        is_fallback=not llm_ok,
    )
    db.add(assistant_msg)

    # 13. Track token usage
    if token_info:
        from app.models.token_usage import TokenUsage
        usage = TokenUsage(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            usage_type="chat",
            model=token_info.model,
            prompt_tokens=token_info.prompt_tokens,
            completion_tokens=token_info.completion_tokens,
            total_tokens=token_info.total_tokens,
        )
        db.add(usage)

    # 14. Update conversation timestamp
    conversation.last_message_at = datetime.utcnow()
    await db.flush()

    return clean_reply


async def _transcribe_audio(audio_urls: list[str]) -> str | None:
    """Transcribe voice notes using faster-whisper (local, free)."""
    try:
        from app.services.transcription import transcribe_url
        for url in audio_urls[:1]:
            text = await transcribe_url(url)
            if text:
                return text
    except Exception as e:
        logger.warning(f"Voice transcription failed: {e}")
    return None


async def _analyze_images(db: AsyncSession, tenant: Tenant, media_urls: list[str]) -> list:
    """Analyze product images using Gemini Vision (free).

    Writes a TokenUsage row (usage_type="vision") per successful analysis so
    Gemini Vision calls are tracked alongside text-LLM calls.
    """
    from app.config import get_settings
    from app.services.vision import analyze_product_image

    settings = get_settings()
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        return []

    results = []
    for url in media_urls[:3]:
        try:
            result = await analyze_product_image(url, api_key)
            if result:
                results.append(result)
                # Persist token usage for the vision call (best-effort).
                try:
                    from app.models.token_usage import TokenUsage
                    usage = TokenUsage(
                        id=uuid.uuid4(),
                        tenant_id=tenant.id,
                        usage_type="vision",
                        model="gemini-2.0-flash",
                        prompt_tokens=result.prompt_tokens,
                        completion_tokens=result.completion_tokens,
                        total_tokens=result.prompt_tokens + result.completion_tokens,
                    )
                    db.add(usage)
                except Exception as tu_err:
                    logger.warning(f"Failed to track vision token usage: {tu_err}")
        except Exception as e:
            logger.warning(f"Vision analysis failed for {url}: {e}")
    return results


async def _get_or_create_customer(
    db: AsyncSession, tenant_id: uuid.UUID, psid: str, name: str | None = None,
    channel: str = "messenger",
) -> Customer:
    result = await db.execute(
        select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.fb_psid == psid,
        )
    )
    customer = result.scalar_one_or_none()

    if not customer:
        customer = Customer(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            fb_psid=psid,
            name=name or "عميل",
            channel=channel,
        )
        db.add(customer)
        await db.flush()

    return customer


async def _get_or_create_conversation(
    db: AsyncSession, tenant_id: uuid.UUID, customer_id: uuid.UUID,
    channel: str = "messenger",
) -> Conversation:
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.tenant_id == tenant_id,
            Conversation.customer_id == customer_id,
        )
        .order_by(Conversation.started_at.desc())
        .limit(1)
    )
    conversation = result.scalar_one_or_none()

    if conversation:
        if conversation.status != "active":
            conversation.status = "active"
        return conversation

    if not conversation:
        conversation = Conversation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            customer_id=customer_id,
            channel=channel,
        )
        db.add(conversation)
        await db.flush()

    return conversation


async def _load_conversation_history(
    db: AsyncSession, conversation_id: uuid.UUID
) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(MAX_HISTORY_MESSAGES)
    )
    messages = list(result.scalars().all())
    messages.reverse()
    return messages


async def _create_order_from_data(
    db: AsyncSession,
    tenant: Tenant,
    customer: Customer,
    conversation: Conversation,
    order_data: dict,
) -> bool:
    """Create an order from extracted AI data. Returns True on success, False on failure."""
    from app.services.order_service import create_order
    from app.services.notification_service import notify_new_order
    from app.models.product import Product

    order_items = order_data.get("items", [])
    items = []
    for item in order_items:
        product_name = item["product_name"]
        quantity = item.get("quantity", 1)

        # Audit H4: escape LIKE wildcards — a product_name of "%%" used to
        # match the FIRST product in the catalog (attacker-steerable pick).
        escaped = product_name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        result = await db.execute(
            select(Product).where(
                Product.tenant_id == tenant.id,
                Product.is_active == True,
                Product.name.ilike(f"%{escaped}%", escape="\\"),
            ).limit(1)
        )
        matching = result.scalar_one_or_none()

        if matching:
            attrs = matching.attributes or {}
            unit_price = attrs.get("discount_price") or matching.price
        else:
            # Audit H4: hallucinated/unmatched products must NOT become
            # zero-priced order lines. The whole order is rejected — the
            # customer is told the item isn't available (better than a
            # silent 0-EGP order the merchant must unwind).
            logger.warning(
                "Order rejected: product %r not in tenant catalog",
                product_name,
            )
            return False

        items.append({
            # Keep the UUID object — OrderItem.product_id is typed as
            # ``Mapped[Optional[uuid.UUID]]`` and SQLAlchemy's Uuid type
            # expects a real UUID object (it calls ``.hex`` on it).
            # Stringifying here used to work on asyncpg (lenient) but
            # crashes SQLite and other stricter dialects.
            "product_id": matching.id,
            "product_name": product_name,
            "quantity": quantity,
            "unit_price": unit_price,
        })

    if not items:
        logger.warning("No items in order data")
        return False

    # Update customer details — Audit M3: NEVER overwrite collected PII with
    # None. The LLM frequently emits partial order JSON (items only), which
    # used to wipe previously-collected phone/governorate/city/address.
    customer.name = order_data.get("customer_name") or customer.name
    customer.phone = order_data.get("customer_phone") or customer.phone
    customer.governorate = order_data.get("governorate") or customer.governorate
    customer.city = order_data.get("city") or customer.city
    customer.area = order_data.get("area") or customer.area
    customer.address_detail = order_data.get("address_detail") or customer.address_detail

    first_product = None
    if items[0].get("product_id"):
        result = await db.execute(
            select(Product).where(
                Product.id == items[0]["product_id"],
                Product.tenant_id == tenant.id,
            )
        )
        first_product = result.scalar_one_or_none()

    try:
        order = await create_order(
            db=db,
            tenant_id=tenant.id,
            customer_id=customer.id,
            conversation_id=conversation.id,
            customer_name=order_data["customer_name"],
            customer_phone=order_data["customer_phone"],
            governorate=order_data.get("governorate", ""),
            city=order_data.get("city", ""),
            area=order_data.get("area"),
            address_detail=order_data["address_detail"],
            payment_method=order_data.get("payment_method", "cod"),
            items=items,
            delivery_charge=_calc_delivery(tenant, order_data.get("governorate", ""), items, first_product),
        )

        logger.info(f"Order {order.order_number} created: {len(items)} items")

        # Dispatch notification via the Huey queue when a consumer is alive;
        # fall back to a direct await when it isn't (single-process mode) so
        # we never silently swallow a brand-new order.
        try:
            from app.tasks.huey_app import huey_consumer_running
            from app.tasks.notification_tasks import send_order_notification
            if huey_consumer_running():
                # Huey semantics: calling the task ENQUEUES it (durable).
                send_order_notification(str(tenant.id), str(order.id))
            else:
                await notify_new_order(tenant, order)
        except Exception as notify_err:
            logger.warning(
                f"Huey notification dispatch failed ({notify_err}); falling "
                f"back to synchronous notify_new_order"
            )
            try:
                await notify_new_order(tenant, order)
            except Exception as e:
                logger.error(f"Failed to notify order: {e}")

    except Exception as e:
        logger.error(f"Failed to create order: {e}")
        return False

    return True


def _calc_delivery(tenant: Tenant, governorate: str, items: list[dict], product=None):
    """Calculate delivery charge for Egyptian governorates."""
    from decimal import Decimal

    if product and product.attributes:
        prod_delivery = product.attributes.get("delivery_charge")
        if prod_delivery is not None:
            return Decimal(str(prod_delivery))
        if product.attributes.get("free_delivery"):
            return Decimal("0")

    subtotal = sum(Decimal(str(i.get("unit_price", 0))) * i.get("quantity", 1) for i in items)
    if tenant.free_delivery_above and subtotal >= tenant.free_delivery_above:
        return Decimal("0")

    # Cairo/Giza = inside, rest = outside
    is_cairo = governorate.lower() in ("cairo", "giza", "القاهرة", "الجيزة")
    if is_cairo:
        return Decimal(str(tenant.delivery_inside_cairo or 35))
    return Decimal(str(tenant.delivery_outside_cairo or 60))


def _get_fallback_response(language: str) -> str:
    """Fallback response when LLM is unavailable."""
    if language == "arabic":
        return "لو سمحت، مقدرش أرد دلوقتي. جرب تاني بعد شوية. 🙏"
    elif language == "arabizi":
        return "Sorry, msh a2dar arud dilwaqti. Try tani ba3d shwaya. 🙏"
    else:
        return "Sorry, I'm unable to respond at the moment. Please try again shortly. 🙏"
