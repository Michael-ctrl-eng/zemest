"""Facebook Page management — webhook subscription, page listing, catalog sync.

All Graph calls go through :mod:`app.services.graph_client` — Bearer
header only (tokens NEVER in URLs — audit A4-H2 / D4-G5), keep-alive
connection, single v22.0 version constant.
"""
import logging

from app.config import get_settings
from app.services.graph_client import graph_get, graph_post

logger = logging.getLogger(__name__)
settings = get_settings()


async def get_user_pages(user_access_token: str) -> list[dict]:
    """Get list of Facebook pages managed by user."""
    data = await graph_get(
        "me/accounts",
        token=user_access_token,
        fields="id,name,access_token",
    )
    return data.get("data", [])


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
    result = await graph_post(
        f"{page_id}/subscribed_apps",
        token=page_access_token,
        json_body={"subscribed_fields": subscribed_fields},
    )
    if result or result == {}:
        # graph_post returns {} on failure; success returns {"success": true}.
        if result:
            logger.info("Page %s subscribed to webhook fields: %s", page_id, subscribed_fields)
            return True
    logger.warning("subscribe_page_to_webhook failed for page %s", page_id)
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
    result = await graph_post(
        f"{ig_user_id}/subscribed_apps",
        token=access_token,
        json_body={"subscribed_fields": subscribed_fields},
    )
    if result:
        logger.info("Instagram %s subscribed: %s", ig_user_id, subscribed_fields)
        return True
    logger.warning("subscribe_instagram failed for %s", ig_user_id)
    return False


async def get_page_products(page_id: str, page_access_token: str) -> list[dict]:
    """Fetch products from Facebook page's product catalog."""
    catalogs = (await graph_get(
        f"{page_id}/product_catalogs",
        token=page_access_token,
    )).get("data", [])
    if not catalogs:
        return []

    catalog_id = catalogs[0]["id"]
    products = (await graph_get(
        f"{catalog_id}/products",
        token=page_access_token,
        fields="id,name,description,price,image_url,availability",
    )).get("data", [])
    return products
