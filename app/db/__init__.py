# Версия файла: 1.1.1
# Описание: Инициализация БД (SQLAlchemy async engine + session) как пакет db
# Дата изменения: 2025-12-27

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import settings

logger = logging.getLogger("db")


class Base(DeclarativeBase):
    """Базовый класс для ORM-моделей."""
    pass


# Создаём асинхронный движок SQLAlchemy
engine: AsyncEngine = create_async_engine(
    settings.database_dsn(),
    pool_pre_ping=True,
    echo=False,
)

# Фабрика асинхронных сессий
SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def init_db() -> None:
    """
    Создаёт таблицы в базе данных (миграции будут добавлены позднее).
    Импорт моделей внутри функции предотвращает циклические зависимости.
    """
    # Импортируем ORM-модели, чтобы SQLAlchemy знал о них
    from .models import MarketplaceAccount, User  # noqa: F401

    async with engine.begin() as conn:
        # Создаём таблицы, если их ещё нет
        await conn.run_sync(Base.metadata.create_all)

    logger.info("DB initialized (tables ensured)")
