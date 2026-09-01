"""Build the REAL system prompt the agent will send to the LLM, from the
LIVE tenant's silently-learned profile — proof the learned style reaches
the reply path end-to-end."""
import asyncio
import os
import sys

REPO = "/home/z/my-project/repos/zemest"
sys.path.insert(0, REPO)
os.chdir(REPO)
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./zemest_local.db"

from sqlalchemy import select
from app.database import async_session
from app.models.tenant import Tenant
from app.ai.prompts import get_system_prompt


async def main():
    async with async_session() as db:
        tenant = (await db.execute(
            select(Tenant).where(Tenant.page_name == "Cairo Sneakers")
        )).scalar_one()
        prompt = get_system_prompt(
            business_name=tenant.page_name,
            products_context="- Nike Air Max 90 White: 1250 ج.م",
            style_profile=tenant.style_profile or {},
            dialect="egyptian",
        )
        print(prompt)
        print()
        print("=" * 70)
        checks = {
            "greeting learned": "أهلا" in prompt,
            "exemplar few-shot": "رد الصفحة: أهلاً بيك، متوفر بـ 1250 جنيه" in prompt,
            "buyer persona section": "عملاء الصفحة" in prompt,
            "franco guidance": "فرانكو" in prompt,
            "length guidance": "حرف" in prompt,
            "vocabulary": "جنيه" in prompt,
        }
        for k, v in checks.items():
            print(("PASS " if v else "FAIL ") + k)
        assert all(checks.values()), "some learned-style elements missing from prompt"


asyncio.run(main())
