from fastapi import APIRouter

from app.api import auth, tenants, products, orders, conversations, customers, address, crawl, webhook, facebook, test_chat
from app.api import style_learning, scheduling, postiz, demo_chat, channels, calendar, payments

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(tenants.router)
api_router.include_router(products.router)
api_router.include_router(orders.router)
api_router.include_router(conversations.router)
api_router.include_router(customers.router)
api_router.include_router(address.router)
api_router.include_router(crawl.router)
api_router.include_router(webhook.router)
api_router.include_router(facebook.router)
api_router.include_router(test_chat.router)
api_router.include_router(style_learning.router)
api_router.include_router(scheduling.router)
api_router.include_router(postiz.router)
api_router.include_router(demo_chat.router)
api_router.include_router(channels.router)
api_router.include_router(calendar.router)
api_router.include_router(payments.router)
