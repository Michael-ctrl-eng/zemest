from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

_db_url = settings.DATABASE_URL

# SQLite (tests / local dev) uses NullPool and rejects pool_size/max_overflow;
# Postgres/MySQL in production get a real connection pool.
if _db_url.startswith("sqlite"):
    engine = create_async_engine(_db_url, echo=settings.APP_DEBUG)
else:
    engine = create_async_engine(
        _db_url,
        echo=settings.APP_DEBUG,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
