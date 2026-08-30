"""API endpoints for chat history import and style learning.

POST /api/tenants/{tenant_id}/import/chat-history
  - Accepts ZIP file upload (FB DYI / IG DYI / WhatsApp Export)
  - Parses locally (zero ban risk)
  - Imports messages to DB
  - Triggers style profile build
  - Returns the style profile

GET /api/tenants/{tenant_id}/style-profile
  - Returns the current style profile

POST /api/tenants/{tenant_id}/rebuild-style
  - Rebuilds style profile from existing messages
"""
from __future__ import annotations

import io
import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_tenant
from app.models.tenant import Tenant
from app.services.importers.messenger_dyi import (
    get_zip_stats,
    parse_instagram_dyi_zip,
    parse_messenger_dyi_zip,
)
from app.services.importers.whatsapp_export import parse_whatsapp_export_zip
from app.ai.style_learner import build_and_persist_personality

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants/{tenant_id}", tags=["Style Learning"])

# Max upload size: 500 MB (DYI exports can be large)
MAX_UPLOAD_SIZE = 500 * 1024 * 1024


@router.post("/import/chat-history")
async def import_chat_history(
    file: UploadFile = File(...),
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    channel: str = "auto",
):
    """Upload a chat history ZIP file and build the style profile.

    Supports:
    - Facebook Messenger DYI export (JSON format)
    - Instagram DYI export (JSON format — same as FB)
    - WhatsApp "Export Chat" ZIP

    The `channel` query param can be: 'messenger', 'instagram', 'whatsapp', or 'auto'.
    Auto-detection is based on file contents.

    Zero ban risk: we parse the uploaded file locally — no API calls to Meta.
    """
    # Read the uploaded file
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max {MAX_UPLOAD_SIZE // (1024*1024)} MB.",
        )

    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")

    # Get stats first (quick peek)
    stats = get_zip_stats(contents)

    # Auto-detect channel if not specified
    detected_channel = channel
    if channel == "auto":
        if file.filename and "whatsapp" in file.filename.lower():
            detected_channel = "whatsapp"
        elif stats.get("thread_count", 0) > 0:
            # Has messenger-style JSON files
            detected_channel = "messenger"
        else:
            # Try WhatsApp format (has _chat.txt)
            import zipfile
            try:
                with zipfile.ZipFile(io.BytesIO(contents)) as zf:
                    if any(n.endswith(".txt") for n in zf.namelist()):
                        detected_channel = "whatsapp"
                    else:
                        detected_channel = "messenger"
            except zipfile.BadZipFile:
                raise HTTPException(status_code=400, detail="Invalid ZIP file")

    # Parse based on channel
    try:
        if detected_channel == "whatsapp":
            messages = parse_whatsapp_export_zip(contents)
        elif detected_channel == "instagram":
            messages = parse_instagram_dyi_zip(contents)
        else:  # messenger
            messages = parse_messenger_dyi_zip(contents)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not messages:
        raise HTTPException(
            status_code=400,
            detail="No messages found in the uploaded file. Please ensure you exported in JSON format.",
        )

    # Import messages and build style profile
    from app.ai.style_learner import import_messages_and_build_style

    result = await import_messages_and_build_style(
        db=db,
        tenant=tenant,
        messages=messages,
        channel=detected_channel,
    )

    return {
        "status": "success",
        "channel": detected_channel,
        "imported_messages": result["imported"],
        "style_profile": result["style_profile"],
        "zip_stats": stats,
    }


@router.get("/style-profile")
async def get_style_profile(
    tenant: Tenant = Depends(get_tenant),
):
    """Get the current style profile for this tenant."""
    if not tenant.style_profile:
        return {
            "status": "not_built",
            "message": "No style profile yet. Upload chat history to build one.",
            "profile": None,
        }

    return {
        "status": "built",
        "built_at": tenant.knowledge_built_at.isoformat() if tenant.knowledge_built_at else None,
        "profile": tenant.style_profile,
    }


@router.post("/rebuild-style")
async def rebuild_style(
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    use_llm: bool = True,
):
    """Rebuild the style profile from existing messages in the DB.

    This re-analyzes all merchant messages and rebuilds the style profile.
    Useful after new messages have been captured via webhooks.
    """
    profile = await build_and_persist_personality(db, tenant, use_llm=use_llm)

    return {
        "status": "rebuilt",
        "profile": profile,
    }
