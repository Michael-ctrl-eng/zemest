"""WhatsApp Business API client.

All calls use the shared :mod:`app.services.graph_client` (keep-alive,
Bearer-only, single version constant — audit D4-G11: the hardcoded
``v21.0`` is rejected by Meta since 2025-09-09).
"""
import logging

from app.services.graph_client import graph_post
from app.services import graph_client as _gc

logger = logging.getLogger(__name__)

# Backwards-compatible constant: now derived from the shared client's
# single version constant instead of a second hardcoded copy.
WHATSAPP_API_URL = f"https://graph.facebook.com/{_gc.GRAPH_API_VERSION}"


async def send_whatsapp_message(tenant, recipient_id: str, text: str) -> bool:
    """Send a text message via WhatsApp Business API."""
    token = tenant.wa_access_token
    if not token:
        logger.warning("No WhatsApp access token configured")
        return False

    result = await graph_post(
        f"{tenant.wa_phone_number_id}/messages",
        token=token,
        json_body={
            "messaging_product": "whatsapp",
            "to": recipient_id,
            "type": "text",
            "text": {"body": text},
        },
    )
    return bool(result)


async def resolve_media(tenant, media_id: str) -> dict:
    """Resolve a WhatsApp media ID to its metadata (url, mime, sha256, size).

    Audit D4-M1: WhatsApp Cloud API webhooks deliver MEDIA IDS, not URLs —
    the platform was passing IDs to vision/transcription as if they were
    URLs (silently broken). The real flow: resolve the ID here, then
    download ``url`` with the same Bearer token (valid ~5 minutes).
    """
    token = tenant.wa_access_token
    if not token or not media_id:
        return {}
    from app.services.graph_client import graph_get

    return await graph_get(media_id, token=token)
