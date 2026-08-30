from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="dashboard/templates")

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"], include_in_schema=False)


@dashboard_router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@dashboard_router.get("")
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@dashboard_router.get("/{tenant_id}/chat")
async def chat_page(request: Request, tenant_id: str):
    return templates.TemplateResponse(
        "chat.html", {"request": request, "tenant_id": tenant_id}
    )


@dashboard_router.get("/{tenant_id}/products")
async def products_page(request: Request, tenant_id: str):
    return templates.TemplateResponse(
        "products.html", {"request": request, "tenant_id": tenant_id}
    )


@dashboard_router.get("/{tenant_id}/orders")
async def orders_page(request: Request, tenant_id: str):
    return templates.TemplateResponse(
        "orders.html", {"request": request, "tenant_id": tenant_id}
    )


@dashboard_router.get("/{tenant_id}/customers")
async def customers_page(request: Request, tenant_id: str):
    return templates.TemplateResponse(
        "customers.html", {"request": request, "tenant_id": tenant_id}
    )


@dashboard_router.get("/{tenant_id}/conversations")
async def conversations_page(request: Request, tenant_id: str):
    return templates.TemplateResponse(
        "conversations.html", {"request": request, "tenant_id": tenant_id}
    )


@dashboard_router.get("/{tenant_id}/crawl")
async def crawl_page(request: Request, tenant_id: str):
    return templates.TemplateResponse(
        "crawl.html", {"request": request, "tenant_id": tenant_id}
    )


@dashboard_router.get("/{tenant_id}/settings")
async def settings_page(request: Request, tenant_id: str):
    return templates.TemplateResponse(
        "settings.html", {"request": request, "tenant_id": tenant_id}
    )
