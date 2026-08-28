"""Facebook Messenger & Instagram Graph API client.

Handles sending messages, sender actions, and attachments for both
Messenger and Instagram channels — matching Chatwoot's capabilities.
"""
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Sender actions (typing_on, typing_off, mark_seen)
# ---------------------------------------------------------------------------

async def send_sender_action(page_access_token: str, recipient_id: str, action: str) -> bool:
    """Send a sender action (typing_on, typing_off, mark_seen)."""
    url = f"{settings.FB_GRAPH_API_URL}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "sender_action": action,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                url, json=payload,
                params={"access_token": page_access_token},
            )
            return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Sender action '{action}' failed: {e}")
        return False


async def typing_on(token: str, recipient_id: str) -> bool:
    return await send_sender_action(token, recipient_id, "typing_on")


async def typing_off(token: str, recipient_id: str) -> bool:
    return await send_sender_action(token, recipient_id, "typing_off")


async def mark_seen(token: str, recipient_id: str) -> bool:
    return await send_sender_action(token, recipient_id, "mark_seen")


# ---------------------------------------------------------------------------
# Text messages
# ---------------------------------------------------------------------------

async def send_text_message(
    page_access_token: str,
    recipient_id: str,
    text: str,
    messaging_type: str = "RESPONSE",
    tag: str | None = None,
) -> dict:
    """Send a text message via Facebook Messenger / Instagram Graph API.

    If tag is provided, uses MESSAGE_TAG messaging_type (needed for >24h window).
    """
    url = f"{settings.FB_GRAPH_API_URL}/me/messages"
    payload: dict = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": messaging_type,
    }
    if tag and messaging_type == "MESSAGE_TAG":
        payload["tag"] = tag
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url, json=payload,
                params={"access_token": page_access_token},
            )
            data = resp.json()

            if resp.status_code != 200:
                error = data.get("error", {})
                error_code = error.get("code", 0)
                error_msg = error.get("message", "")
                if error_code in (190, 10):
                    logger.error(
                        f"AUTH ERROR sending message: code={error_code} "
                        f"msg={error_msg}. Token may be expired or revoked."
                    )
                    data["_auth_error"] = True
                else:
                    logger.warning(f"send_text_message API error: {resp.status_code} {error_msg}")

            if "message_id" in data:
                data["_source_id"] = data["message_id"]

            return data
    except httpx.TimeoutException:
        logger.error("send_text_message timed out")
        return {}
    except Exception as e:
        logger.error(f"send_text_message failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# Quick replies
# ---------------------------------------------------------------------------

async def send_quick_replies(
    page_access_token: str,
    recipient_id: str,
    text: str,
    options: list[str],
) -> dict:
    """Send a message with quick reply buttons."""
    url = f"{settings.FB_GRAPH_API_URL}/me/messages"
    quick_replies = [
        {"content_type": "text", "title": opt, "payload": opt} for opt in options[:13]
    ]
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text, "quick_replies": quick_replies},
        "messaging_type": "RESPONSE",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url, json=payload,
                params={"access_token": page_access_token},
            )
            return resp.json()
    except Exception as e:
        logger.error(f"send_quick_replies failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# Attachment messages (images, audio, video, files)
# ---------------------------------------------------------------------------

async def send_attachment(
    page_access_token: str,
    recipient_id: str,
    attachment_type: str,
    url: str,
) -> dict:
    """Send an attachment (image, audio, video, file)."""
    valid_types = {"image", "audio", "video", "file"}
    if attachment_type not in valid_types:
        attachment_type = "file"

    api_url = f"{settings.FB_GRAPH_API_URL}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": attachment_type,
                "payload": {"url": url},
            }
        },
        "messaging_type": "RESPONSE",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                api_url, json=payload,
                params={"access_token": page_access_token},
            )
            data = resp.json()

            if resp.status_code != 200:
                error = data.get("error", {})
                error_code = error.get("code", 0)
                if error_code in (190, 10):
                    logger.error(f"AUTH ERROR sending attachment: code={error_code}")
                    data["_auth_error"] = True
                else:
                    logger.warning(f"send_attachment API error: {resp.status_code} {error.get('message', '')}")

            return data
    except httpx.TimeoutException:
        logger.error("send_attachment timed out")
        return {}
    except Exception as e:
        logger.error(f"send_attachment failed: {e}")
        return {}


async def send_image(page_access_token: str, recipient_id: str, image_url: str) -> dict:
    return await send_attachment(page_access_token, recipient_id, "image", image_url)


async def send_audio(page_access_token: str, recipient_id: str, audio_url: str) -> dict:
    return await send_attachment(page_access_token, recipient_id, "audio", audio_url)


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------

async def get_user_profile(page_access_token: str, psid: str) -> dict:
    """Get user profile info from Facebook."""
    url = f"{settings.FB_GRAPH_API_URL}/{psid}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                url,
                params={
                    "access_token": page_access_token,
                    "fields": "first_name,last_name,profile_pic",
                },
            )
            if resp.status_code == 200:
                return resp.json()
            return {}
    except Exception as e:
        logger.warning(f"get_user_profile failed: {e}")
        return {}
