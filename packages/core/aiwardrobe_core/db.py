from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from aiwardrobe_core.config import Settings, get_settings


class Base(DeclarativeBase):
    pass


def create_engine(settings: Settings | None = None) -> AsyncEngine:
    resolved = settings or get_settings()
    return create_async_engine(resolved.database_url, pool_pre_ping=True)


engine = create_engine()
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
