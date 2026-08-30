import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.utils.security import create_access_token, hash_password, verify_password

settings = get_settings()


async def register_user(db: AsyncSession, name: str, email: str, password: str) -> User:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ValueError("Email already registered")

    user = User(
        id=uuid.uuid4(),
        name=name,
        email=email,
        hashed_password=hash_password(password),
    )
    db.add(user)
    await db.flush()
    return user


async def login_user(db: AsyncSession, email: str, password: str) -> str:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.hashed_password:
        raise ValueError("Invalid credentials")
    if not verify_password(password, user.hashed_password):
        raise ValueError("Invalid credentials")

    return create_access_token({"sub": str(user.id)})


async def login_with_facebook(db: AsyncSession, fb_access_token: str) -> str:
    """Exchange FB user token for our JWT."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.FB_GRAPH_API_URL}/me",
            params={"access_token": fb_access_token, "fields": "id,name,email"},
        )
        if resp.status_code != 200:
            raise ValueError("Invalid Facebook token")
        fb_data = resp.json()

    result = await db.execute(
        select(User).where(User.fb_user_id == fb_data["id"])
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            id=uuid.uuid4(),
            fb_user_id=fb_data["id"],
            name=fb_data.get("name", ""),
            email=fb_data.get("email"),
        )
        db.add(user)
        await db.flush()

    return create_access_token({"sub": str(user.id)})
