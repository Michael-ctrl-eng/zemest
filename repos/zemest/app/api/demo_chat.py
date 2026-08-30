"""
Public demo-chat endpoint for the landing-page "Talk to Agent" widget.

- NO authentication (it's a public marketing demo — no user data involved)
- NO LLM calls — replies come from the pure-Python rule-based demo_agent
  (microseconds of CPU per message, effectively zero cost at any scale)
- Rate-limited per IP so playful bots can't spam it
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.services import demo_agent

try:
    from app.middleware.rate_limit import get_limiter as _get_limiter
    _limiter = _get_limiter()
except Exception:  # noqa: BLE001
    _limiter = None

router = APIRouter(prefix="/api/demo", tags=["Demo"])


class DemoChatRequest(BaseModel):
    session_id: str = Field(min_length=6, max_length=64)
    message: str = Field(min_length=1, max_length=500)
    tz: str | None = Field(default=None, max_length=64)


class WelcomeRequest(BaseModel):
    session_id: str = Field(min_length=6, max_length=64)
    tz: str | None = Field(default=None, max_length=64)


class DemoChatResponse(BaseModel):
    reply: str
    image: str | None = None
    quick_replies: list[str] = []
    order_done: bool = False
    is_arabic: bool = False


@router.post("/chat", response_model=DemoChatResponse)
@_limiter.limit("30/minute")
async def demo_chat(request: Request, req: DemoChatRequest):
    # tz = visitor's IANA timezone from the browser -> local currency & city
    result = demo_agent.build_reply(req.message, req.session_id, req.tz)
    return DemoChatResponse(
        reply=result["reply"],
        image=result.get("image"),
        quick_replies=result.get("quick_replies", []),
        order_done=result.get("order_done", False),
        is_arabic=demo_agent.is_arabic(req.message),
    )


@router.post("/welcome", response_model=DemoChatResponse)
@_limiter.limit("10/minute")
async def demo_welcome(request: Request, req: WelcomeRequest):
    return DemoChatResponse(**demo_agent.welcome(req.session_id, req.tz))
