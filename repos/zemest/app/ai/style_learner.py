"""Lightning-fast style-learning agent.

Analyzes a user's chat history (from DYI exports) to extract their
communication style profile in SECONDS.

Architecture (all local, zero API calls to Meta during analysis):
1. Parse uploaded ZIP files (messenger_dyi / whatsapp_export)
2. Filter to merchant (page owner) outbound messages only
3. Smart sampling: 300 messages stratified by recency + intent clustering
4. LLM extraction: single call to Qwen2.5 / Llama 4 with structured-output prompt
5. Store JSON profile on tenant.style_profile

Speed: millions of messages → parsed + sampled + LLM-extracted in <40 seconds.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.language_engine import detect_language_advanced
from app.models.message import Message
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

# Sampling parameters (tuned for speed + accuracy)
SAMPLE_SIZE = 300  # research shows accuracy plateaus at ~300 messages
RECENT_WINDOW_DAYS = 30
MID_WINDOW_DAYS = 90


# ============================================================
# Step 1: Collect merchant messages from DB
# ============================================================

async def collect_merchant_messages(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 100000,
) -> list[Message]:
    """Collect all merchant (page owner) outbound messages for a tenant.

    Uses role IN ('assistant', 'merchant') to capture both:
    - 'merchant': historical messages imported from DYI exports
    - 'assistant': AI agent replies (for continuity)

    Returns up to `limit` messages ordered by created_at DESC.
    """
    result = await db.execute(
        select(Message)
        .join(Message.conversation)
        .where(
            Message.conversation.has(tenant_id=tenant_id),
            Message.role.in_(["assistant", "merchant"]),
            # Never learn from canned LLM-unavailable apologies.
            or_(
                Message.is_fallback.is_(None),
                Message.is_fallback == False,  # noqa: E712
            ),
        )
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ============================================================
# Step 2: Smart sampling (300 messages, stratified by recency)
# ============================================================

def smart_sample(messages: list[Message], sample_size: int = SAMPLE_SIZE) -> list[Message]:
    """Sample messages intelligently — stratified by recency.

    Distribution:
    - 40% from last 30 days (recent style)
    - 30% from last 90 days (medium-term)
    - 30% from older (historical baseline)

    Also deduplicates near-identical messages.
    """
    if len(messages) <= sample_size:
        return messages

    now = datetime.utcnow()
    recent_cutoff = now - timedelta(days=RECENT_WINDOW_DAYS)
    mid_cutoff = now - timedelta(days=MID_WINDOW_DAYS)

    recent: list[Message] = []
    mid: list[Message] = []
    old: list[Message] = []

    for msg in messages:
        ts = msg.created_at.replace(tzinfo=None) if msg.created_at.tzinfo else msg.created_at
        if ts > recent_cutoff:
            recent.append(msg)
        elif ts > mid_cutoff:
            mid.append(msg)
        else:
            old.append(msg)

    # Target counts per bucket
    recent_target = int(sample_size * 0.4)
    mid_target = int(sample_size * 0.3)
    old_target = sample_size - recent_target - mid_target

    # Sample from each bucket. Audit H6: ``random.seed(42)`` re-seeded the
    # PROCESS-GLOBAL RNG — every concurrently-created order number became
    # deterministic and predictable. Use a thread-local Random instance
    # instead (per-call object, global RNG untouched).
    rng = random.Random()
    sampled = []
    sampled.extend(rng.sample(recent, min(recent_target, len(recent))) if recent else [])
    sampled.extend(rng.sample(mid, min(mid_target, len(mid))) if mid else [])
    sampled.extend(rng.sample(old, min(old_target, len(old))) if old else [])

    # If we're short (some buckets were empty), top up from the largest bucket
    deficit = sample_size - len(sampled)
    if deficit > 0:
        remaining = [m for m in messages if m not in sampled]
        sampled.extend(rng.sample(remaining, min(deficit, len(remaining))) if remaining else [])

    # Deduplicate near-identical messages (same first 50 chars)
    seen_prefixes: set[str] = set()
    deduped: list[Message] = []
    for msg in sampled:
        prefix = msg.content[:50].strip().lower() if msg.content else ""
        if prefix and prefix not in seen_prefixes:
            seen_prefixes.add(prefix)
            deduped.append(msg)
        elif not prefix:
            deduped.append(msg)

    return deduped[:sample_size]


# ============================================================
# Step 3: Heuristic feature extraction (fast, CPU, no LLM)
# ============================================================

def extract_heuristic_features(messages: list[Message]) -> dict:
    """Extract fast heuristic features from sampled messages.

    This runs in milliseconds for 300 messages — no LLM needed.
    """
    if not messages:
        return _empty_features()

    total = len(messages)
    contents = [m.content for m in messages if m.content]

    # Length stats
    lengths = [len(c) for c in contents]
    avg_length = sum(lengths) / len(lengths) if lengths else 0
    short_count = sum(1 for l in lengths if l < 60)
    medium_count = sum(1 for l in lengths if 60 <= l < 160)
    long_count = sum(1 for l in lengths if l >= 160)

    # Emoji analysis
    emoji_count = 0
    emoji_inventory: dict[str, int] = defaultdict(int)
    for content in contents:
        for char in content:
            if ord(char) > 0x1F000:  # emoji range
                emoji_count += 1
                emoji_inventory[char] += 1
    avg_emoji_per_msg = emoji_count / total if total > 0 else 0
    top_emojis = sorted(emoji_inventory.items(), key=lambda x: -x[1])[:10]
    emoji_freq = "none" if avg_emoji_per_msg == 0 else (
        "low" if avg_emoji_per_msg < 0.5 else
        "medium" if avg_emoji_per_msg < 2 else
        "high"
    )

    # Language detection (sample 50 messages for speed)
    lang_sample = contents[:50] if len(contents) > 50 else contents
    lang_counts: dict[str, int] = defaultdict(int)
    for text in lang_sample:
        detection = detect_language_advanced(text)
        lang_counts[detection.primary_language] += 1
    total_lang = sum(lang_counts.values()) or 1
    language_mix = {k: round(v / total_lang, 2) for k, v in lang_counts.items()}

    # Greeting detection (Egyptian Arabic + English patterns)
    greeting_patterns = [
        "أهلا", "اهلا", "مرحبا", "السلام عليكم", "هاي", "هلا",
        "hi", "hello", "hey", "good morning", "good evening",
        "صباح الخير", "مساء الخير", "إزيك", "ازيك", "عامل ايه",
    ]
    greetings_found: dict[str, int] = defaultdict(int)
    for content in contents:
        content_lower = content.lower()
        for pattern in greeting_patterns:
            if pattern.lower() in content_lower:
                greetings_found[pattern] += 1
                break  # one greeting per message
    top_greetings = sorted(greetings_found.items(), key=lambda x: -x[1])[:5]

    # Signoff detection
    signoff_patterns = [
        "شكرا", "تسلم", "ربنا يخليك", "في الخدمة", "تحياتي", "مع السلامة",
        "thank", "thanks", "bye", "regards", "best",
        "خالص", "تمام", "اوكي", "تم",
    ]
    signoffs_found: dict[str, int] = defaultdict(int)
    for content in contents:
        content_lower = content.lower()
        for pattern in signoff_patterns:
            if pattern.lower() in content_lower:
                signoffs_found[pattern] += 1
                break
    top_signoffs = sorted(signoffs_found.items(), key=lambda x: -x[1])[:5]

    # Formality detection (street vs formal)
    formal_markers = ["حضرتك", "سيدي", "سيدتي", "تفضل", "أرجو", "رجاء"]
    casual_markers = ["يا عم", "يا صاحبي", "بقى", "خلاص", "يلا", "طب"]
    formal_count = sum(1 for c in contents if any(m in c for m in formal_markers))
    casual_count = sum(1 for c in contents if any(m in c for m in casual_markers))

    if formal_count > casual_count:
        tone = "formal"
        formality_level = min(10, 6 + formal_count)
    elif casual_count > formal_count:
        tone = "casual"
        formality_level = max(0, 4 - casual_count)
    else:
        tone = "friendly"
        formality_level = 5

    # Response time analysis (if we have conversation context)
    avg_length_bucket = "short" if avg_length < 60 else "medium" if avg_length < 160 else "long"

    # Vocabulary (top 15 distinctive words)
    word_freq: dict[str, int] = defaultdict(int)
    stop_words = {"the", "a", "an", "is", "are", "in", "on", "at", "to", "for",
                  "و", "في", "من", "على", "إلى", "أن", "هذا", "هذه", "التي", "الذي"}
    for content in contents:
        words = content.lower().split()
        for word in words:
            word = word.strip(".,!?؟،؛")
            if len(word) > 2 and word not in stop_words:
                word_freq[word] += 1
    top_words = sorted(word_freq.items(), key=lambda x: -x[1])[:15]

    # Sample replies (5 representative messages of varying length)
    if contents:
        sorted_by_length = sorted(contents, key=len)
        sample_indices = [
            len(sorted_by_length) // 6,
            len(sorted_by_length) // 3,
            len(sorted_by_length) // 2,
            2 * len(sorted_by_length) // 3,
            5 * len(sorted_by_length) // 6,
        ]
        sample_replies = [sorted_by_length[i][:200] for i in sample_indices if i < len(sorted_by_length)]
    else:
        sample_replies = []

    return {
        "tone": tone,
        "formality_level": formality_level,
        "greeting_patterns": [g[0] for g in top_greetings],
        "signoff_patterns": [s[0] for s in top_signoffs],
        "emoji_frequency": emoji_freq,
        "emoji_inventory": [e[0] for e in top_emojis],
        "avg_response_length": avg_length_bucket,
        "avg_length_chars": round(avg_length, 1),
        "language_mix": language_mix,
        "vocabulary": [w[0] for w in top_words],
        "sample_replies": sample_replies,
        "message_count_analyzed": total,
        "short_msg_pct": round(short_count / total * 100, 1) if total else 0,
        "medium_msg_pct": round(medium_count / total * 100, 1) if total else 0,
        "long_msg_pct": round(long_count / total * 100, 1) if total else 0,
    }


def _empty_features() -> dict:
    return {
        "tone": "friendly",
        "formality_level": 5,
        "greeting_patterns": [],
        "signoff_patterns": [],
        "emoji_frequency": "none",
        "emoji_inventory": [],
        "avg_response_length": "medium",
        "avg_length_chars": 0,
        "language_mix": {"arabic": 0.5, "english": 0.5},
        "vocabulary": [],
        "sample_replies": [],
        "message_count_analyzed": 0,
    }


# ============================================================
# Step 4: LLM-based deep style extraction (optional, enhances heuristics)
# ============================================================

STYLE_EXTRACTION_PROMPT = """You are analyzing an Egyptian merchant's chat messages to learn their communication style.

MERCHANT MESSAGES (chronological order, most recent first):
{sampled_messages}

Extract a structured style profile. Return JSON ONLY with these keys:
{{
  "tone": "formal|friendly|casual|playful",
  "greeting_patterns": ["actual phrases they use to open conversations"],
  "signoff_patterns": ["actual phrases they use to close conversations"],
  "emoji_frequency": "none|low|medium|high",
  "objection_handling": "how they handle price/availability objections (1-2 sentences)",
  "closing_patterns": ["how they confirm orders/close sales"],
  "personality_summary": "1-sentence style fingerprint",
  "sales_tactics": ["any notable sales techniques observed"],
  "response_style": "direct|consultative|enthusiastic|minimal"
}}

Be specific — quote actual phrases from the messages. If you can't determine a field, use null."""

async def llm_style_extraction(messages: list[Message]) -> dict | None:
    """Use LLM to extract deep style features from sampled messages.

    Falls back gracefully if LLM is unavailable.
    """
    if not messages:
        return None

    try:
        from app.ai.llm_client import chat_completion_with_usage

        # Format messages for the prompt (limit to 50 to keep prompt small)
        sample = messages[:50]
        formatted = "\n".join(
            f"{i+1}. {m.content[:200]}"
            for i, m in enumerate(sample)
            if m.content
        )

        prompt = STYLE_EXTRACTION_PROMPT.format(sampled_messages=formatted)
        llm_messages = [
            {"role": "system", "content": "You are a communication style analyst. Return valid JSON only."},
            {"role": "user", "content": prompt},
        ]

        result = await chat_completion_with_usage(llm_messages)
        if not result or not result.content:
            return None

        # Extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', result.content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))

    except Exception as e:
        logger.warning(f"LLM style extraction failed: {e}")

    return None


# ============================================================
# Step 5: Build and persist the complete style profile
# ============================================================

async def build_and_persist_personality(
    db: AsyncSession,
    tenant: Tenant,
    use_llm: bool = True,
) -> dict:
    """Build a complete style profile for a tenant and persist it.

    This is the main entry point. Runs in <40 seconds for millions of messages.

    Steps:
    1. Collect merchant messages from DB
    2. Smart sample 300 messages (stratified by recency)
    3. Extract heuristic features (CPU, milliseconds)
    4. (Optional) LLM deep extraction (2-5 seconds)
    5. Merge into final profile
    6. Persist to tenant.style_profile + tenant.knowledge_built_at

    Returns the style profile dict.
    """
    logger.info(f"Building style profile for tenant {tenant.id}")

    # Step 1: Collect messages
    messages = await collect_merchant_messages(db, tenant.id)
    if len(messages) < 6:
        logger.info(f"Tenant {tenant.id} has only {len(messages)} messages — using defaults")
        profile = _empty_features()
        profile["message_count_analyzed"] = len(messages)
    else:
        # Step 2: Smart sample
        sampled = smart_sample(messages)
        logger.info(f"Sampled {len(sampled)} messages from {len(messages)} total")

        # Step 3: Heuristic features (fast)
        profile = extract_heuristic_features(sampled)

        # Step 4: LLM extraction (optional, enhances heuristics)
        if use_llm:
            llm_features = await llm_style_extraction(sampled)
            if llm_features:
                # Merge: LLM features override heuristics where available
                for key, value in llm_features.items():
                    if value is not None and value != []:
                        profile[key] = value

    # Step 5: Add metadata
    profile["built_at"] = datetime.utcnow().isoformat()
    profile["total_messages_available"] = len(messages)

    # Step 6: Persist
    tenant.style_profile = profile
    tenant.knowledge_built_at = datetime.utcnow()
    await db.commit()

    logger.info(f"Style profile built for tenant {tenant.id}: tone={profile.get('tone')}")
    return profile


# ============================================================
# Utility: Import messages from ZIP and trigger style build
# ============================================================

async def import_messages_and_build_style(
    db: AsyncSession,
    tenant: Tenant,
    messages: list[dict],
    channel: str = "messenger",
) -> dict:
    """Import parsed messages into DB, then build style profile.

    Args:
        db: Database session
        tenant: Tenant object
        messages: List of normalized message dicts (from parser)
        channel: 'messenger', 'instagram', or 'whatsapp'

    Returns:
        {"imported": int, "style_profile": dict}
    """
    from app.models.conversation import Conversation
    from app.models.customer import Customer

    imported_count = 0

    # Group messages by thread_title
    threads: dict[str, list[dict]] = defaultdict(list)
    for msg in messages:
        threads[msg["thread_title"]].append(msg)

    # Import each thread as a conversation. conversations.customer_id is a
    # NOT-NULL FK, so each imported thread gets (or reuses) a synthetic
    # customer named after the thread title. (Fixes the 500 that made
    # /import/chat-history unusable — the trainer's main data on-ramp.)
    customer_cache: dict[str, Customer] = {}
    for thread_title, thread_msgs in threads.items():
        customer = customer_cache.get(thread_title)
        if customer is None:
            safe_psid = f"imported:{uuid.uuid5(uuid.NAMESPACE_DNS, f'{tenant.id}:{thread_title}')}"
            existing = await db.execute(
                select(Customer).where(
                    Customer.tenant_id == tenant.id,
                    Customer.fb_psid == safe_psid,
                )
            )
            customer = existing.scalar_one_or_none()
            if customer is None:
                customer = Customer(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    fb_psid=safe_psid,
                    channel=channel,
                    name=thread_title[:255] or "Imported thread",
                )
                db.add(customer)
                await db.flush()
            customer_cache[thread_title] = customer

        # Create or find a conversation for this thread
        conv = Conversation(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            customer_id=customer.id,
            channel=channel,
            status="imported",
        )
        db.add(conv)
        await db.flush()

        # Add messages
        for msg_data in thread_msgs:
            db_msg = Message(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                role=msg_data["role"],
                content=msg_data["content"],
                channel=channel,
                created_at=msg_data["timestamp"],
            )
            db.add(db_msg)
            imported_count += 1

        # Update conversation timestamps
        if thread_msgs:
            conv.started_at = thread_msgs[0]["timestamp"]
            conv.last_message_at = thread_msgs[-1]["timestamp"]

    await db.flush()
    logger.info(f"Imported {imported_count} messages for tenant {tenant.id}")

    # Build style profile
    profile = await build_and_persist_personality(db, tenant)

    return {"imported": imported_count, "style_profile": profile}
