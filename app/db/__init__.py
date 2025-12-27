# Версия файла: 2.2.0
# Описание: Инициализация базы данных и фабрика асинхронных сессий.
#           Добавлены: db_ping(), мягкие миграции (ensure_schema) для добавления колонок в существующие таблицы.
# Дата изменения: 2025-12-28

from __future__ import annotations

import logging

from sqlalchemy import text
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
    """Базовый класс для всех ORM-моделей."""
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


async def db_ping() -> bool:
    """
    Быстрая проверка доступности БД для /health.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("DB ping failed")
        return False


async def _column_exists(conn: AsyncSession, table: str, column: str) -> bool:
    sql = text(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = :table
          AND column_name = :column
        LIMIT 1
        """
    )
    res = await conn.execute(sql, {"table": table, "column": column})
    return res.scalar_one_or_none() is not None


async def ensure_schema() -> None:
    """
    Мягкие миграции без Alembic:
    - добавляем отсутствующие колонки, которые появились в моделях,
      но таблицы были созданы ранее.

    Сейчас требуется:
    - users.updated_at
    """
    async with SessionLocal() as session:
        # users.updated_at
        try:
            exists = await _column_exists(session, "users", "updated_at")
            if not exists:
                logger.warning("Schema migration: add column users.updated_at")
                await session.execute(
                    text(
                        """
                        ALTER TABLE public.users
                        ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        """
                    )
                )
                await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Schema ensure failed (users.updated_at)")


async def init_db() -> None:
    """
    Создаёт таблицы в базе данных, если они отсутствуют, и применяет мягкие миграции.

    При использовании Alembic этот метод должен быть заменён миграциями,
    но сейчас мы поддерживаем additive-изменения схемы.
    """
    # ВАЖНО: сначала обеспечим схему для уже существующих таблиц.
    await ensure_schema()

    # Импортируем модели, чтобы зарегистрировать в metadata
    from .models import MarketplaceCredential, OrderEvent, User  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("DB initialized (tables ensured)")
