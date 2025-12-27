# Версия файла: 2.0.0
# Описание: Инициализация базы данных и фабрика асинхронных сессий.
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
    """Базовый класс для всех ORM‑моделей."""
    pass


# Создаём асинхронный движок SQLAlchemy. DSN берётся из конфигурации
engine: AsyncEngine = create_async_engine(
    settings.database_dsn(),
    pool_pre_ping=True,
    echo=False,
)

# Фабрика асинхронных сессий. expire_on_commit=False исключает автоматическое
# обновление объектов после коммита, что упрощает работу в рамках одной сессии.
SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def init_db() -> None:
    """
    Создаёт таблицы в базе данных, если они отсутствуют.

    Импорт моделей находится внутри функции, чтобы избежать циклических
    зависимостей. При использовании Alembic этот метод можно
    заменить миграциями.
    """
    # Импортируем модели для регистрации в metadata. noqa используется для
    # подавления предупреждений линтера о неиспользуемых переменных.
    from .models import MarketplaceCredential, OrderEvent, User  # noqa: F401

    async with engine.begin() as conn:
        # Создаём все таблицы, если их ещё нет
        await conn.run_sync(Base.metadata.create_all)

    logger.info("DB initialized (tables ensured)")