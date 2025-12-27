# Версия файла: 1.1.0
# Описание: Инициализация БД (SQLAlchemy async engine + session)
# Дата изменения: 2025-12-27

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

logger = logging.getLogger("db")


class Base(DeclarativeBase):
    pass


engine: AsyncEngine = create_async_engine(
    settings.database_dsn(),
    pool_pre_ping=True,
    echo=False,
)

SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def init_db() -> None:
    """
    Создаёт таблицы (миграции добавим на следующем этапе).
    """
    from db.models import MarketplaceAccount, User  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("DB initialized (tables ensured)")
