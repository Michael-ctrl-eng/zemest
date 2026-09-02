"""Facebook Page management — webhook subscription, page listing, catalog sync.

All Graph calls now go through :mod:`app.services.graph_client`
(Bearer-only Authorization header — tokens never ride in URL query
strings where proxies/logs/browser history capture them; audit A4-H2).
"""
import logging

from app.config import get_settings
from app.services.graph_client import GraphAPIError, graph_get, graph_post

logger = logging.getLogger(__name__)
settings = get_settings()


async def get_user_pages(user_access_token: str) -> list[dict]:
    """Get list of Facebook pages managed by user."""
    try:
        data = await graph_get(
            "me/accounts",
            user_access_token,
            fields="id,name,access_token",
        )
        return data.get("data", [])
    except GraphAPIError as e:
        logger.warning(f"get_user_pages failed: {e.status_code} {e.detail}")
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
    subscribed_fields = [
        "messages",
        "message_deliveries",
        "message_echoes",
        "message_reads",
        "messaging_postbacks",
        "standby",
    ]
    try:
        await graph_post(
            f"{page_id}/subscribed_apps",
            page_access_token,
            json={"subscribed_fields": subscribed_fields},
        )
        logger.info(f"Page {page_id} subscribed to webhook fields: {subscribed_fields}")
        return True
    except GraphAPIError as e:
        logger.warning(f"subscribe_page_to_webhook failed: {e.status_code} {e.detail}")
        return False


async def subscribe_instagram_to_webhook(ig_user_id: str, access_token: str) -> bool:
    """Subscribe an Instagram Business account to receive webhook events.

    Instagram-specific fields (matching Chatwoot):
    - messages: incoming DMs
    - message_reactions: reactions on messages
    - messaging_seen: read receipts
    """
    subscribed_fields = [
        "messages",
        "message_reactions",
        "messaging_seen",
    ]
    try:
        await graph_post(
            f"{ig_user_id}/subscribed_apps",
            access_token,
            json={"subscribed_fields": subscribed_fields},
        )
        logger.info(f"Instagram {ig_user_id} subscribed: {subscribed_fields}")
        return True
    except GraphAPIError as e:
        logger.warning(f"subscribe_instagram failed: {e.status_code} {e.detail}")
        return False


async def get_page_products(page_id: str, page_access_token: str) -> list[dict]:
    """Fetch products from Facebook page's product catalog."""
    try:
        catalogs = await graph_get(
            f"{page_id}/product_catalogs",
            page_access_token,
        )
        entries = catalogs.get("data", [])
        if not entries:
            return []
        catalog_id = entries[0]["id"]
        products = await graph_get(
            f"{catalog_id}/products",
            page_access_token,
            fields="id,name,description,price,image_url,availability",
        )
        return products.get("data", [])
    except GraphAPIError as e:
        logger.warning(f"get_page_products error: {e.status_code} {e.detail}")
        return []
    except Exception as e:
        logger.error(f"get_page_products error: {e}")
        return []

    catalog_id = catalogs[0]["id"]
    products = (await graph_get(
        f"{catalog_id}/products",
        token=page_access_token,
        fields="id,name,description,price,image_url,availability",
    )).get("data", [])
    return products
