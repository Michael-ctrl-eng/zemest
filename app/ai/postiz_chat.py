"""Postiz AI Chat Agent — two-way conversation between Zemest and Postiz.

This module lets our AI agent:
1. Receive Postiz's AI-generated post ideas
2. Enhance them with the tenant's style profile
3. Send back improved captions for scheduling
4. Handle user requests like "create a post about X" by delegating to Postiz AI
5. Coordinate between our chat agent (customer-facing) and Postiz (content creation)

Architecture:
    Customer ↔ Zemest ↔ Postiz AI
                    ↓
              Style Profile
              (tenant.voice)
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from app.ai.language_engine import detect_language_advanced
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


# ============================================================
# Postiz AI Chat Integration
# ============================================================

async def handle_postiz_chat_request(
    tenant: Tenant,
    user_message: str,
    user_id: str,
) -> dict:
    """Handle a chat request that may involve Postiz AI.

    This is called when the user asks the agent to do something related to
    social media scheduling (e.g., "write a post about X", "schedule a post",
    "what's my best time to post?").

    Returns a dict with:
    - reply: str (the agent's response to show the user)
    - action: str (what was done: "generated", "scheduled", "insights", "unknown")
    - data: dict (any structured data returned)
    """
    detection = detect_language_advanced(user_message)
    lang = detection.primary_language

    # Detect intent
    intent = _detect_intent(user_message)

    if intent == "generate_post":
        return await _handle_generate_post(tenant, user_message, lang)
    elif intent == "schedule_post":
        return await _handle_schedule_post(tenant, user_message, lang)
    elif intent == "best_time":
        return await _handle_best_time(tenant, lang)
    elif intent == "insights":
        return await _handle_insights(tenant, lang)
    elif intent == "list_posts":
        return await _handle_list_posts(tenant, lang)
    else:
        # Not a Postiz request — let the normal agent handle it
        return {
            "reply": None,  # signal: not handled
            "action": "unknown",
            "data": {},
        }


def _detect_intent(message: str) -> str:
    """Detect what the user wants to do related to social media."""
    msg_lower = message.lower()

    # Arabic + English patterns
    generate_patterns = [
        "اكتب بوست", "اكتب منشور", "اكتب كابشن", "ولّد بوست", "اعمل بوست",
        "write a post", "generate a post", "create a caption", "make a post",
        "write content", "come up with a post",
    ]
    schedule_patterns = [
        "جدول بوست", "انشر بوست", "جدولة منشور", "نشر منشور",
        "schedule a post", "publish a post", "post this", "schedule this",
    ]
    best_time_patterns = [
        "أفضل وقت", "وقت النشر", "أفضل وقت للنشر", "امتى أنشر",
        "best time", "when to post", "best time to post",
    ]
    insights_patterns = [
        "إحصائيات", "تحليلات", "أداء", "إحصائيات البوستات",
        "insights", "analytics", "statistics", "performance", "how are my posts",
    ]
    list_patterns = [
        "البوستات بتاعتي", "المنشورات", "بوستاتي", "شوف البوستات",
        "my posts", "list posts", "show posts", "scheduled posts",
    ]

    for p in generate_patterns:
        if p in msg_lower:
            return "generate_post"
    for p in schedule_patterns:
        if p in msg_lower:
            return "schedule_post"
    for p in best_time_patterns:
        if p in msg_lower:
            return "best_time"
    for p in insights_patterns:
        if p in msg_lower:
            return "insights"
    for p in list_patterns:
        if p in msg_lower:
            return "list_posts"

    return "unknown"


# ============================================================
# Intent handlers
# ============================================================

async def _handle_generate_post(tenant: Tenant, message: str, lang: str) -> dict:
    """Handle 'generate a post' requests by delegating to Postiz AI or our LLM."""
    # Extract the topic from the message
    topic = _extract_topic(message, lang)

    # Try Postiz AI first
    try:
        from app.scheduling.postiz_client import get_postiz_client
        client = get_postiz_client()
        results = await client.generate_posts(
            prompt=topic,
            number_of_posts=3,
        )

        if results:
            captions = []
            for r in results:
                if isinstance(r, dict) and "content" in r:
                    captions.append(r["content"])
                elif isinstance(r, str):
                    captions.append(r)

            if captions:
                reply = _format_generated_posts(captions, lang)
                return {
                    "reply": reply,
                    "action": "generated",
                    "data": {"captions": captions, "source": "postiz"},
                }
    except Exception as e:
        logger.warning(f"Postiz AI generation failed, falling back to our LLM: {e}")

    # Fallback: use our own LLM
    try:
        from app.ai.llm_client import chat_completion_with_usage

        style_hint = ""
        if tenant.style_profile:
            p = tenant.style_profile
            style_hint = f"\nStyle: tone={p.get('tone')}, emoji={p.get('emoji_frequency')}"

        prompt = f"""Generate 3 social media post captions about: {topic}
{style_hint}
Language: {lang}
Return JSON: {{"captions": ["caption1", "caption2", "caption3"]}}"""

        result = await chat_completion_with_usage([
            {"role": "system", "content": "You are a social media content creator. Return valid JSON only."},
            {"role": "user", "content": prompt},
        ])

        json_match = re.search(r'\{.*\}', result.content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            captions = data.get("captions", [])
            reply = _format_generated_posts(captions, lang)
            return {
                "reply": reply,
                "action": "generated",
                "data": {"captions": captions, "source": "zemest_llm"},
            }
    except Exception as e:
        logger.error(f"LLM caption generation failed: {e}")

    # Final fallback
    if lang == "arabic":
        return {
            "reply": "مقدرش أكتب البوست دلوقتي، حاول تاني بعد شوية 🙏",
            "action": "error",
            "data": {},
        }
    return {
        "reply": "Sorry, I couldn't generate posts right now. Please try again. 🙏",
        "action": "error",
        "data": {},
    }


async def _handle_schedule_post(tenant: Tenant, message: str, lang: str) -> dict:
    """Handle 'schedule a post' requests."""
    # Check if Postiz is available
    try:
        from app.scheduling.postiz_client import get_postiz_client
        client = get_postiz_client()
        integrations = await client.list_integrations()

        if not integrations:
            reply = (
                "لم تقم بربط أي حسابات تواصل اجتماعي بعد. "
                "اربط صفحتك على فيسبوك أو انستجرام أولاً من إعدادات الجدولة."
                if lang == "arabic"
                else "You haven't connected any social accounts yet. "
                     "Connect your FB Page or Instagram first in the scheduling settings."
            )
            return {"reply": reply, "action": "no_integrations", "data": {}}

        # List available accounts
        accounts = [
            f"• {i.get('identifier', 'Unknown')} ({i.get('provider', 'unknown')})"
            for i in integrations
        ]
        reply = (
            f"لديك {len(integrations)} حسابات متصلة:\n" + "\n".join(accounts) +
            "\n\nقولي إيه البوست اللي عايز تنشره وأمتى."
            if lang == "arabic"
            else f"You have {len(integrations)} connected accounts:\n" + "\n".join(accounts) +
                 "\n\nTell me what you want to post and when."
        )
        return {
            "reply": reply,
            "action": "awaiting_post_details",
            "data": {"integrations": integrations},
        }
    except Exception as e:
        logger.error(f"Postiz schedule_post failed: {e}")
        return {
            "reply": "مقدرش أوصل لخدمة الجدولة دلوقتي 🙏" if lang == "arabic" else "Can't reach the scheduling service right now 🙏",
            "action": "error",
            "data": {},
        }


async def _handle_best_time(tenant: Tenant, lang: str) -> dict:
    """Handle 'best time to post' requests."""
    try:
        from app.scheduling.postiz_client import get_postiz_client
        client = get_postiz_client()
        slot = await client.find_free_slot()

        if slot:
            reply = (
                f"أفضل وقت لنشر بوستك القادم: {slot}"
                if lang == "arabic"
                else f"Best time for your next post: {slot}"
            )
            return {"reply": reply, "action": "best_time", "data": {"slot": slot}}
    except Exception as e:
        logger.warning(f"Postiz best-time failed: {e}")

    # Fallback: use our native IG insights
    try:
        from app.scheduling.instagram_publisher import get_best_time_to_post
        if tenant.ig_user_id and tenant.ig_access_token:
            result = await get_best_time_to_post(tenant.ig_access_token, tenant.ig_user_id)
            top_slots = result.get("top_slots", [])
            if top_slots:
                slots_text = "\n".join(
                    f"• {s['day']} {s['formatted_time']} (score: {s['score']})"
                    for s in top_slots[:3]
                )
                reply = (
                    f"أفضل أوقات النشر:\n{slots_text}"
                    if lang == "arabic"
                    else f"Best times to post:\n{slots_text}"
                )
                return {"reply": reply, "action": "best_time", "data": result}
    except Exception as e:
        logger.error(f"IG best-time failed: {e}")

    return {
        "reply": "مقدرش أجيب أوقات النشر دلوقتي 🙏" if lang == "arabic" else "Can't fetch best-time data right now 🙏",
        "action": "error",
        "data": {},
    }


async def _handle_insights(tenant: Tenant, lang: str) -> dict:
    """Handle 'show insights' requests."""
    try:
        from app.scheduling.postiz_client import get_postiz_client
        client = get_postiz_client()
        posts = await client.list_posts(filter_type="published", limit=10)

        if posts and posts.get("posts"):
            post_list = posts["posts"][:5]
            lines = []
            for p in post_list:
                caption = p.get("caption", "")[:50] + "..." if len(p.get("caption", "")) > 50 else p.get("caption", "")
                stats = p.get("stats", {})
                impressions = stats.get("impressions", "N/A")
                lines.append(f"• {caption} — impressions: {impressions}")

            reply = (
                f"آخر بوستاتك المنشورة:\n" + "\n".join(lines)
                if lang == "arabic"
                else f"Your recent published posts:\n" + "\n".join(lines)
            )
            return {"reply": reply, "action": "insights", "data": posts}
        else:
            reply = (
                "مفيش بوستات منشورة لسه 📭"
                if lang == "arabic"
                else "No published posts yet 📭"
            )
            return {"reply": reply, "action": "insights", "data": {}}
    except Exception as e:
        logger.error(f"Postiz insights failed: {e}")
        return {
            "reply": "مقدرش أجيب الإحصائيات دلوقتي 🙏" if lang == "arabic" else "Can't fetch insights right now 🙏",
            "action": "error",
            "data": {},
        }


async def _handle_list_posts(tenant: Tenant, lang: str) -> dict:
    """Handle 'list my posts' requests."""
    try:
        from app.scheduling.postiz_client import get_postiz_client
        client = get_postiz_client()
        posts = await client.list_posts(filter_type="scheduled", limit=10)

        if posts and posts.get("posts"):
            post_list = posts["posts"]
            lines = []
            for p in post_list:
                caption = p.get("caption", "")[:60]
                scheduled = p.get("scheduled_at", "")[:16]
                lines.append(f"• {caption} — {scheduled}")

            reply = (
                f"البوستات المجدولة ({len(post_list)}):\n" + "\n".join(lines)
                if lang == "arabic"
                else f"Scheduled posts ({len(post_list)}):\n" + "\n".join(lines)
            )
            return {"reply": reply, "action": "list_posts", "data": posts}
        else:
            reply = "مفيش بوستات مجدولة لسه" if lang == "arabic" else "No scheduled posts yet"
            return {"reply": reply, "action": "list_posts", "data": {}}
    except Exception as e:
        logger.error(f"Postiz list_posts failed: {e}")
        return {
            "reply": "مقدرش أجيب قائمة البوستات دلوقتي 🙏" if lang == "arabic" else "Can't fetch posts list right now 🙏",
            "action": "error",
            "data": {},
        }


# ============================================================
# Helpers
# ============================================================

def _extract_topic(message: str, lang: str) -> str:
    """Extract the topic from a 'write a post about X' message."""
    # Arabic patterns
    ar_patterns = [
        r"اكتب بوست عن (.+)",
        r"اكتب منشور عن (.+)",
        r"اكتب كابشن عن (.+)",
        r"ولّد بوست عن (.+)",
        r"اعمل بوست عن (.+)",
    ]
    # English patterns
    en_patterns = [
        r"write a post about (.+)",
        r"generate a post about (.+)",
        r"create a caption about (.+)",
        r"make a post about (.+)",
        r"write content about (.+)",
    ]

    patterns = ar_patterns + en_patterns if lang != "english" else en_patterns
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Fallback: return the whole message
    return message


def _format_generated_posts(captions: list[str], lang: str) -> str:
    """Format generated captions into a chat-friendly reply."""
    if not captions:
        return "مقدرش أولّد بوستات دلوقتي 🙏" if lang == "arabic" else "Couldn't generate posts right now 🙏"

    header = "إليك 3 اقتراحات للبوست:\n\n" if lang == "arabic" else "Here are 3 post ideas:\n\n"
    lines = []
    for i, caption in enumerate(captions, 1):
        lines.append(f"{i}. {caption}\n")
    footer = "\nقولي رقم البوست اللي عجبك وأنا أجدوله لك! 📅" if lang == "arabic" else "\nTell me which one you like and I'll schedule it! 📅"

    return header + "\n".join(lines) + footer
