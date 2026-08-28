"""WhatsApp Business API client."""

import logging

import httpx

logger = logging.getLogger(__name__)

WHATSAPP_API_URL = "https://graph.facebook.com/v21.0"


async def send_whatsapp_message(tenant, recipient_id: str, text: str) -> bool:
    """Send a text message via WhatsApp Business API."""
    token = tenant.wa_access_token
    if not token:
        logger.warning("No WhatsApp access token configured")
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{WHATSAPP_API_URL}/{tenant.wa_phone_number_id}/messages",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": recipient_id,
                    "type": "text",
                    "text": {"body": text},
                },
            )
            if resp.status_code == 200:
                return True
            logger.warning(f"WhatsApp send failed: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.error(f"WhatsApp send error: {e}")
        return False
