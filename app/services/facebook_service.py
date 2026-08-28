"""Facebook Page management — webhook subscription, page listing, catalog sync."""
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def get_user_pages(user_access_token: str) -> list[dict]:
    """Get list of Facebook pages managed by user."""
    url = f"{settings.FB_GRAPH_API_URL}/me/accounts"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                url,
                params={"access_token": user_access_token, "fields": "id,name,access_token"},
            )
            if resp.status_code == 200:
                return resp.json().get("data", [])
            logger.warning(f"get_user_pages failed: {resp.status_code}")
            return []
    except Exception as e:
        logger.error(f"get_user_pages error: {e}")
        return []


async def subscribe_page_to_webhook(page_id: str, page_access_token: str) -> bool:
    """Subscribe a page to receive webhook events.

    Subscribes to the same fields Chatwoot uses:
    - messages: incoming messages
    - message_deliveries: delivery receipts
    - message_echoes: outgoing message echoes (so we can skip our own)
    - message_reads: read receipts
    - messaging_postbacks: button click postbacks
    - standby: standby queue for handover protocol
    """
    url = f"{settings.FB_GRAPH_API_URL}/{page_id}/subscribed_apps"
    subscribed_fields = [
        "messages",
        "message_deliveries",
        "message_echoes",
        "message_reads",
        "messaging_postbacks",
        "standby",
    ]
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                params={"access_token": page_access_token},
                json={"subscribed_fields": subscribed_fields},
            )
            if resp.status_code == 200:
                logger.info(f"Page {page_id} subscribed to webhook fields: {subscribed_fields}")
                return True
            logger.warning(f"subscribe_page_to_webhook failed: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.error(f"subscribe_page_to_webhook error: {e}")
        return False


async def subscribe_instagram_to_webhook(ig_user_id: str, access_token: str) -> bool:
    """Subscribe an Instagram Business account to receive webhook events.

    Instagram-specific fields (matching Chatwoot):
    - messages: incoming DMs
    - message_reactions: reactions on messages
    - messaging_seen: read receipts
    """
    url = f"{settings.FB_GRAPH_API_URL}/{ig_user_id}/subscribed_apps"
    subscribed_fields = [
        "messages",
        "message_reactions",
        "messaging_seen",
    ]
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                params={"access_token": access_token},
                json={"subscribed_fields": subscribed_fields},
            )
            if resp.status_code == 200:
                logger.info(f"Instagram {ig_user_id} subscribed: {subscribed_fields}")
                return True
            logger.warning(f"subscribe_instagram failed: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.error(f"subscribe_instagram error: {e}")
        return False


async def get_page_products(page_id: str, page_access_token: str) -> list[dict]:
    """Fetch products from Facebook page's product catalog."""
    url = f"{settings.FB_GRAPH_API_URL}/{page_id}/product_catalogs"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                url, params={"access_token": page_access_token},
            )
            if resp.status_code != 200:
                return []

            catalogs = resp.json().get("data", [])
            if not catalogs:
                return []

            catalog_id = catalogs[0]["id"]
            products_url = f"{settings.FB_GRAPH_API_URL}/{catalog_id}/products"
            resp = await client.get(
                products_url,
                params={
                    "access_token": page_access_token,
                    "fields": "id,name,description,price,image_url,availability",
                },
            )
            if resp.status_code == 200:
                return resp.json().get("data", [])
            return []
    except Exception as e:
        logger.error(f"get_page_products error: {e}")
        return []
