"""Silent Trainer — the agent that trains itself while nobody is watching.

What the user asked for, in one sentence: the platform's agent should
AUTOMATICALLY and INVISIBLY train itself on every chat — separate the
junk chats (owner chatting with a friend) from the work chats, learn
the buyers' language and the page's voice, recover from crashes by
itself, keep going until properly trained, and handle brand-new pages
with almost no messages.

Design (all of this runs with ZERO user action and ZERO dashboard UI):

1. DISCOVER  — scan every conversation of every active tenant.
2. CLASSIFY  — chat_classifier labels each thread commerce / junk /
               mixed; junk is excluded from learning forever.
3. EXTRACT   — from commerce chats only:
                 • merchant voice (greetings, tone, emoji, length,
                   vocabulary — reuses style_learner heuristics)
                 • buyer persona  (language mix, dialect, arabizi ratio,
                   top opening questions, emoji habits)
                 • exemplar pairs (customer msg → how this page actually
                   replied) used as few-shot style anchors at reply time
4. CONSOLIDATE — merge into tenant.style_profile with drift-resistant
               smoothing; optional one-shot LLM deep-extract when an
               OPENROUTER_API_KEY exists (heuristics otherwise).
5. CHECKPOINT — progress is committed GRANULARLY: every batch of
               classified conversations + every rebuilt profile is
               committed immediately. A crash at any point loses
               nothing — the next cycle resumes exactly where it
               stopped (already-classified threads are skipped, the
               profile is deterministic on the same inputs).
6. SELF-HEAL — per-tenant error backoff with automatic reset on the
               first success; the loop itself can never die. If the
               whole backend is reaped, the platform's fetchWithHeal
               revives the daemon and the trainer resumes from state.
7. MATURITY  — the profile has a maturity score; the trainer keeps
               refining (stage "learning") until thresholds are met,
               then switches to cheap maintenance mode (stage "mature",
               throttled cadence, still picks up every new message).

Everything is stored on existing tenant columns (style_profile,
training_state) and new conversation columns (classification_*) — no
user-facing surface exposes this machinery.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chat_classifier import CLASSIFIER_VERSION, Classification, classify_messages, is_commerce
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

TRAINER_VERSION = "st-2"

# Cadence / batch knobs (cheap by design — heuristic CPU only)
CLASSIFY_BATCH = 50          # conversations classified per commit chunk
CLASSIFY_BATCH_COMMIT = 25   # commit every N classifications (granular checkpoint)
MAX_CONVS_PER_CYCLE = 400    # conversations examined per tenant per cycle
MAX_MSGS_PER_CONV = 200      # messages per conversation used for classification
MAX_MSGS_FOR_PROFILE = 4000  # total messages loaded for profile extraction
MIN_MERCHANT_FOR_VOICE = 6   # below this → cold-start seed voice
MATURE_THRESHOLD = 0.75

# Buyer-persona extraction budget (detect_language_advanced is fast but
# not free — cap the sample)
LANG_SAMPLE_CAP = 120

_BACKOFF_BASE_MIN = 5.0      # minutes; doubles per consecutive error
_BACKOFF_MAX_MIN = 240.0
_MATURE_THROTTLE_MIN = 10.0  # mature tenants: one maintenance pass / 10 min


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

async def run_training_cycle_once(db: AsyncSession) -> dict:
    """One trainer cycle across every active tenant. Returns a summary."""
    result = await db.execute(select(Tenant).where(Tenant.is_active == True))  # noqa: E712
    tenants = list(result.scalars().all())

    summary = {
        "tenants": 0,
        "classified": 0,
        "commerce": 0,
        "junk": 0,
        "profiles_built": 0,
        "skipped": 0,
        "errors": 0,
    }

    for tenant in tenants:
        try:
            tenant_summary = await run_tenant_cycle(db, tenant)
            for k in summary:
                summary[k] += tenant_summary.get(k, 0)
            summary["tenants"] += 1
        except Exception as e:  # noqa: BLE001 — one tenant must never kill the loop
            logger.exception(f"Silent trainer: tenant {tenant.id} cycle failed")
            await _record_error(db, tenant, e)
            summary["errors"] += 1

    return summary


async def run_tenant_cycle(db: AsyncSession, tenant: Tenant) -> dict:
    """One incremental training cycle for a single tenant.

    Cheap when nothing changed (a heartbeat), full pipeline when new
    messages/conversations appeared, self-healing when it previously
    failed (backoff + automatic reset).
    """
    now = datetime.utcnow()
    state: dict = dict(tenant.training_state or {})
    out = {"classified": 0, "commerce": 0, "junk": 0, "profiles_built": 0, "skipped": 0}

    # --- backoff gate (self-heal: retry later, earlier on fewer errors) ---
    next_attempt = _parse_dt(state.get("next_attempt_at"))
    if next_attempt and now < next_attempt:
        out["skipped"] = 1
        return out

    # --- 1+2. classify everything new/changed (commits in chunks) ---
    classified, commerce, junk, conversation_counts = await _classify_tenant_conversations(db, tenant, now)
    out["classified"] = classified
    out["commerce"] = commerce
    out["junk"] = junk

    # --- has anything actually changed since the last profile build? ---
    signature = _profile_signature(conversation_counts, tenant.id)
    epochs: int = int(state.get("epochs", 0) or 0)
    same_signature = state.get("profile_signature") == signature

    if classified == 0 and same_signature and epochs > 0:
        # Heartbeat: nothing new. Mature tenants are throttled to a slow
        # maintenance cadence; learning tenants keep scanning every cycle
        # (the pending-scan query is cheap and new messages must not wait).
        state.update({
            "version": TRAINER_VERSION,
            "last_cycle_at": now.isoformat(),
            "next_attempt_at": (
                (now + timedelta(minutes=_MATURE_THROTTLE_MIN)).isoformat()
                if state.get("stage") == "mature" else None
            ),
        })
        tenant.training_state = state
        await db.commit()
        out["skipped"] = 1
        return out

    # --- 3+4. extract + consolidate (commerce chats only) ---
    profile = await _rebuild_profile(db, tenant, conversation_counts)

    # --- 5+6. checkpoint state, clear error backoff ---
    epochs += 1
    st = profile.get("silent_training", {})
    cstats = profile.get("commerce_stats", {})
    state.update({
        "version": TRAINER_VERSION,
        "stage": st.get("stage", "learning"),
        "maturity": st.get("maturity", 0.0),
        "epochs": epochs,
        "stats": {
            "classified_conversations": conversation_counts.get("total", 0),
            "commerce_conversations": conversation_counts.get("commerce", 0),
            "junk_conversations": conversation_counts.get("junk", 0),
            "merchant_messages": cstats.get("merchant_messages", 0),
            "customer_messages": cstats.get("customer_messages", 0),
            "exemplars": len(profile.get("exemplars", [])),
        },
        "profile_signature": signature,
        "consecutive_errors": 0,
        "next_attempt_at": None,
        "last_success_at": now.isoformat(),
        "last_cycle_at": now.isoformat(),
        "total_errors": int(state.get("total_errors", 0) or 0),
    })

    tenant.training_state = state
    tenant.style_profile = profile
    tenant.knowledge_built_at = now
    await db.commit()

    out["profiles_built"] = 1
    logger.info(
        "Silent trainer: tenant %s epoch %d — %d convs (%d commerce / %d junk), "
        "maturity %.2f, stage %s",
        tenant.id, epochs, conversation_counts.get("total", 0),
        conversation_counts.get("commerce", 0), conversation_counts.get("junk", 0),
        st.get("maturity", 0.0), st.get("stage", "learning"),
    )
    return out


# ---------------------------------------------------------------------------
# Stage 1+2 — classification with granular checkpoints
# ---------------------------------------------------------------------------

async def _classify_tenant_conversations(
    db: AsyncSession, tenant: Tenant, now: datetime
) -> tuple[int, int, int, dict]:
    """Classify every conversation that is new, changed, or classified by an
    older classifier version. Commits every CLASSIFY_BATCH_COMMIT threads so
    a crash loses at most a handful of classifications (the rest resume)."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.tenant_id == tenant.id,
            or_(
                Conversation.classification.is_(None),
                Conversation.classified_by.is_(None),
                Conversation.classified_by != CLASSIFIER_VERSION,
                Conversation.last_message_at > Conversation.classified_at,
            ),
        ).order_by(Conversation.last_message_at.asc()).limit(MAX_CONVS_PER_CYCLE)
    )
    pending = list(result.scalars().all())
    if not pending:
        counts = await _conversation_counts(db, tenant)
        return 0, 0, 0, counts

    done = commerce = junk = 0
    for conv in pending:
        msgs = await db.execute(
            select(Message.role, Message.content)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.asc())
            .limit(MAX_MSGS_PER_CONV)
        )
        payload = [{"role": r[0], "content": r[1]} for r in msgs.all()]
        cls = classify_messages(payload)

        conv.classification = cls.label
        conv.classification_score = float(cls.commerce_score - cls.junk_score)
        conv.classification_signals = {"signals": cls.signals[:12], "commerce": cls.commerce_score,
                                        "junk": cls.junk_score, "confidence": cls.confidence}
        # Monotonic watermark: covers every message up to last_message_at,
        # even if it landed seconds after the cycle started.
        conv.classified_at = max(now, conv.last_message_at) if conv.last_message_at else now
        conv.classified_by = CLASSIFIER_VERSION
        done += 1
        if cls.label == "commerce" or (cls.label == "mixed" and is_commerce(cls.label, cls.commerce_score - cls.junk_score)):
            commerce += 1
        else:
            junk += 1

        if done % CLASSIFY_BATCH_COMMIT == 0:
            await db.commit()  # granular checkpoint — crash-resume boundary

    await db.commit()
    counts = await _conversation_counts(db, tenant)
    return done, commerce, junk, counts


async def _conversation_counts(db: AsyncSession, tenant: Tenant) -> dict:
    rows = await db.execute(
        select(Conversation.classification).where(Conversation.tenant_id == tenant.id)
    )
    counter = Counter(r[0] for r in rows.all())
    commerce = counter.get("commerce", 0) + counter.get("mixed", 0)
    return {
        "total": sum(counter.values()),
        "commerce": commerce,
        "junk": counter.get("junk", 0),
    }


# ---------------------------------------------------------------------------
# Stage 3+4 — profile rebuild (merchant voice + buyer persona + exemplars)
# ---------------------------------------------------------------------------

async def _rebuild_profile(db: AsyncSession, tenant: Tenant, counts: dict) -> dict:
    """Deterministic full rebuild of the tenant's learned profile from
    COMMERCE conversations only. Junk is invisible to the learner."""
    conv_rows = await db.execute(
        select(Conversation.id).where(
            Conversation.tenant_id == tenant.id,
            Conversation.classification.in_(("commerce", "mixed")),
        ).limit(MAX_CONVS_PER_CYCLE)
    )
    conv_ids = [r[0] for r in conv_rows.all()]
    # Exact training-set rule (mixed needs commerce_score - junk_score >= -1)
    commerce_ids = await _filter_commerce_set(db, conv_ids)

    if not commerce_ids:
        profile = _seed_profile(tenant)
        return _finalize(profile, counts, merchant_msgs=0, customer_msgs=0, epochs_delta=True)

    msgs_result = await db.execute(
        select(Message)
        .where(
            Message.conversation_id.in_(commerce_ids),
            Message.role.in_(("merchant", "assistant", "customer")),
            # Canned LLM-unavailable apologies are noise for classification,
            # merchant-voice extraction, and few-shot pairs — skip them all.
            or_(Message.is_fallback.is_(None), Message.is_fallback == False),  # noqa: E712
        )
        .order_by(Message.created_at.asc())
        .limit(MAX_MSGS_FOR_PROFILE)
    )
    messages = list(msgs_result.scalars().all())

    merchant_msgs = [m for m in messages if m.role in ("merchant", "assistant") and (m.content or "").strip()]
    customer_msgs = [m for m in messages if m.role == "customer" and (m.content or "").strip()]

    # ----- merchant voice (reuse the proven style_learner heuristics) -----
    if len(merchant_msgs) >= MIN_MERCHANT_FOR_VOICE:
        from app.ai.style_learner import extract_heuristic_features, smart_sample
        sampled = smart_sample(merchant_msgs)
        voice = extract_heuristic_features(sampled)
    else:
        voice = _seed_voice()

    # ----- buyer persona -----
    buyer = _extract_buyer_persona(customer_msgs)

    # ----- exemplar pairs -----
    exemplars = _extract_exemplars(messages)

    # ----- optional LLM deep extraction (silently skipped without a key) -----
    llm_features = None
    try:
        from app.config import get_settings
        if get_settings().OPENROUTER_API_KEY and len(merchant_msgs) >= MIN_MERCHANT_FOR_VOICE:
            from app.ai.style_learner import llm_style_extraction
            llm_features = await llm_style_extraction(merchant_msgs[:50])
    except Exception as e:  # noqa: BLE001 — enrichment must never block heuristics
        logger.debug(f"Silent trainer: LLM enrichment skipped ({e})")

    # ----- merge (drift-resistant smoothing on numerics) -----
    profile = _merge_profile(tenant.style_profile or {}, voice, buyer, exemplars, llm_features)

    return _finalize(profile, counts, merchant_msgs=len(merchant_msgs),
                     customer_msgs=len(customer_msgs), llm_enriched=bool(llm_features))


async def _filter_commerce_set(db: AsyncSession, conv_ids: list) -> list:
    """Apply the exact is_commerce() rule to mixed conversations."""
    if not conv_ids:
        return []
    rows = await db.execute(
        select(Conversation.id, Conversation.classification, Conversation.classification_score)
        .where(Conversation.id.in_(conv_ids))
    )
    out = []
    for cid, label, score in rows.all():
        if is_commerce(label, float(score or 0.0)):
            out.append(cid)
    return out


def _extract_buyer_persona(customer_msgs: list) -> dict:
    """Who are this page's buyers and how do they talk?"""
    if not customer_msgs:
        return {}

    from app.ai.language_engine import detect_language_advanced

    lang_sample = customer_msgs[-LANG_SAMPLE_CAP:]  # most recent buyers matter most
    lang_counts: Counter = Counter()
    dialect_counts: Counter = Counter()
    for m in lang_sample:
        det = detect_language_advanced((m.content or "")[:200])
        lang_counts[det.primary_language] += 1
        if det.arabic_dialect:
            dialect_counts[det.arabic_dialect] += 1

    total_lang = sum(lang_counts.values()) or 1
    total_dialect = sum(dialect_counts.values()) or 1

    lengths = [len(m.content or "") for m in customer_msgs]
    questions = [m.content for m in customer_msgs if "؟" in (m.content or "") or "?" in (m.content or "")]
    emoji_counts: Counter = Counter()
    for m in lang_sample:
        for ch in m.content or "":
            if ord(ch) > 0x1F000:
                emoji_counts[ch] += 1

    # Top opening lines (buyers' real first words — gold for natural replies)
    openers: Counter = Counter()
    for q in questions[:150]:
        opener = (q or "").strip()[:38]
        if len(opener) >= 8:
            openers[opener] += 1

    arabizi_share = lang_counts.get("arabizi", 0) / total_lang
    return {
        "language_mix": {k: round(v / total_lang, 2) for k, v in lang_counts.most_common(4)},
        "dialects": {k: round(v / total_dialect, 2) for k, v in dialect_counts.most_common(4)},
        "avg_message_chars": round(sum(lengths) / len(lengths), 1),
        "question_rate": round(len(questions) / len(customer_msgs), 2),
        "top_openers": [o for o, _ in openers.most_common(5)],
        "emoji_inventory": [e for e, _ in emoji_counts.most_common(8)],
        "franco_ratio": round(arabizi_share, 2),
        "messages_analyzed": len(customer_msgs),
    }


def _extract_exemplars(messages: list) -> list[dict]:
    """Pick the best (customer question → page reply) pairs from commerce
    chats. These become few-shot style anchors at reply time — this is how
    a brand-new reply 'sounds like the page', not like a chatbot."""
    import re as _re
    from app.ai.chat_classifier import COMMERCE_LEXICON

    strong_tokens = _re.compile("|".join(p for p, _ in COMMERCE_LEXICON.values()), _re.IGNORECASE)

    pairs: list[dict] = []
    prev_customer: Optional[Message] = None
    for m in messages:
        if m.role == "customer":
            prev_customer = m
        elif m.role in ("merchant", "assistant") and prev_customer is not None:
            reply = (m.content or "").strip()
            question = (prev_customer.content or "").strip()
            if 8 <= len(reply) <= 240 and 3 <= len(question) <= 160:
                score = 1.0
                if strong_tokens.search(reply):
                    score += 2.0  # price/delivery/size replies = the page's real sales voice
                if "؟" in question or "?" in question:
                    score += 0.5
                pairs.append({"customer": question, "reply": reply, "score": score})
            prev_customer = None  # one question → one reply

    # Dedup near-identical pairs, keep the highest-scoring
    seen: set[str] = set()
    best: list[dict] = []
    for p in sorted(pairs, key=lambda x: -x["score"]):
        key = p["reply"][:60]
        if key in seen:
            continue
        seen.add(key)
        best.append({"customer": p["customer"][:160], "reply": p["reply"][:220]})
        if len(best) >= 6:
            break
    return best


def _seed_voice() -> dict:
    """Cold-start merchant voice — a natural Egyptian seller, refined the
    moment real merchant messages appear. Used for new pages with few msgs."""
    return {
        "tone": "friendly",
        "formality_level": 4,
        "greeting_patterns": ["أهلاً بيكم", "أهلا"],
        "signoff_patterns": ["تحياتي", "تمام"],
        "emoji_frequency": "low",
        "emoji_inventory": [],
        "avg_response_length": "short",
        "avg_length_chars": 60.0,
        "language_mix": {"arabic": 0.9, "english": 0.1},
        "vocabulary": [],
        "sample_replies": [],
        "seeded": True,
    }


def _seed_profile(tenant: Tenant) -> dict:
    voice = _seed_voice()
    profile = dict(voice)
    profile["buyer_persona"] = {}
    profile["exemplars"] = []
    profile["commerce_stats"] = {"conversations": 0, "junk_filtered": 0,
                                 "merchant_messages": 0, "customer_messages": 0}
    profile["seeded_for"] = str(tenant.id)
    return profile


def _merge_profile(
    previous: dict, voice: dict, buyer: dict, exemplars: list, llm_features: Optional[dict]
) -> dict:
    """Merge the freshly-extracted voice/persona/exemplars into a profile.

    Numerics are smoothed against the previous epoch (drift resistance);
    lists are replaced (full recompute over a superset of the data);
    LLM deep features override heuristics where available.
    """
    profile: dict = dict(voice)
    profile["seeded"] = bool(voice.get("seeded"))  # cold-start marker survives merge

    # Drift-resistant smoothing on numerics (0.7 new / 0.3 old)
    if previous:
        for key in ("avg_length_chars", "formality_level"):
            old = previous.get(key)
            new = profile.get(key)
            if isinstance(old, (int, float)) and isinstance(new, (int, float)):
                profile[key] = round(0.7 * new + 0.3 * old, 1)

    # Prompt-contract keys (singular) so app.ai.prompts consumes them directly
    greetings = profile.get("greeting_patterns") or []
    signoffs = profile.get("signoff_patterns") or []
    profile["greeting_pattern"] = greetings[0] if greetings else ""
    profile["signoff_pattern"] = signoffs[0] if signoffs else ""
    emoji_freq = profile.get("emoji_frequency", "none")
    profile["emoji_use"] = {"none": 0.0, "low": 0.3, "medium": 1.0, "high": 2.0}.get(emoji_freq, 0.0)

    # LLM deep features (objection handling, closing patterns, sales tactics)
    if llm_features:
        for k, v in llm_features.items():
            if v is not None and v != []:
                profile[k] = v

    profile["buyer_persona"] = buyer
    profile["exemplars"] = exemplars
    return profile


def _finalize(
    profile: dict, counts: dict, merchant_msgs: int, customer_msgs: int,
    llm_enriched: bool = False, epochs_delta: bool = True,
) -> dict:
    profile["commerce_stats"] = {
        "conversations": counts.get("commerce", 0),
        "junk_filtered": counts.get("junk", 0),
        "merchant_messages": merchant_msgs,
        "customer_messages": customer_msgs,
    }

    # ----- maturity: "keep going until properly trained" -----
    epochs_hint = 1 if epochs_delta else 0
    checks = {
        "conversations": counts.get("total", 0) >= 5,
        "commerce": counts.get("commerce", 0) >= 2,
        "merchant_messages": merchant_msgs >= 25,
        "customer_messages": customer_msgs >= 20,
        "exemplars": len(profile.get("exemplars", [])) >= 4,
        "epochs": bool(epochs_hint),
    }
    maturity = round(sum(checks.values()) / len(checks), 2)
    stage = "warming" if merchant_msgs < MIN_MERCHANT_FOR_VOICE else (
        "mature" if maturity >= MATURE_THRESHOLD else "learning"
    )

    profile["silent_training"] = {
        "version": TRAINER_VERSION,
        "classifier_version": CLASSIFIER_VERSION,
        "stage": stage,
        "maturity": maturity,
        "maturity_checks": {k: bool(v) for k, v in checks.items()},
        "llm_enriched": llm_enriched,
        "last_epoch_at": datetime.utcnow().isoformat(),
    }
    profile["built_at"] = datetime.utcnow().isoformat()
    profile["message_count_analyzed"] = merchant_msgs + customer_msgs
    profile["total_messages_available"] = merchant_msgs + customer_msgs
    return profile


# ---------------------------------------------------------------------------
# Self-healing helpers
# ---------------------------------------------------------------------------

async def _record_error(db: AsyncSession, tenant: Tenant, exc: Exception) -> None:
    """Record a failed cycle + exponential backoff. The next successful cycle
    clears the backoff automatically — 'turn over and continue where it
    stopped'."""
    now = datetime.utcnow()
    state: dict = dict(tenant.training_state or {})
    consecutive = int(state.get("consecutive_errors", 0) or 0) + 1
    backoff_min = min(_BACKOFF_BASE_MIN * (2 ** (consecutive - 1)), _BACKOFF_MAX_MIN)
    state.update({
        "version": TRAINER_VERSION,
        "consecutive_errors": consecutive,
        "total_errors": int(state.get("total_errors", 0) or 0) + 1,
        "last_error": str(exc)[:300],
        "last_error_at": now.isoformat(),
        "next_attempt_at": (now + timedelta(minutes=backoff_min)).isoformat(),
        "last_cycle_at": now.isoformat(),
    })
    tenant.training_state = state
    try:
        await db.commit()
    except Exception:  # noqa: BLE001 — state write must never mask the original error
        await db.rollback()


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _profile_signature(counts: dict, tenant_id: uuid.UUID) -> str:
    raw = "|".join(str(x) for x in (
        TRAINER_VERSION, CLASSIFIER_VERSION, tenant_id,
        counts.get("total", 0), counts.get("commerce", 0), counts.get("junk", 0),
    ))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
