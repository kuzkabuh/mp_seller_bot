# Версия файла: 2.1.0
# Описание: Инициализация базы данных и фабрика асинхронных сессий (пулы, проверки, корректное завершение).
# Дата изменения: 2025-12-28

from __future__ import annotations

import logging
import os
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
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


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except Exception:
        return default


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "y", "on")


def _get_db_echo() -> bool:
    """
    Управление echo через env:
    - SQLALCHEMY_ECHO=1 включает подробные SQL-логи
    """
    return _bool_env("SQLALCHEMY_ECHO", default=False)


def _get_pool_settings() -> dict:
    """
    Настройки пула соединений через env (без обязательных правок Settings).

    Переменные окружения:
    - DB_POOL_SIZE (по умолчанию 5)
    - DB_MAX_OVERFLOW (по умолчанию 10)
    - DB_POOL_TIMEOUT (по умолчанию 30 секунд)
    - DB_POOL_RECYCLE (по умолчанию 1800 секунд)
    """
    pool_size = _int_env("DB_POOL_SIZE", 5)
    max_overflow = _int_env("DB_MAX_OVERFLOW", 10)
    pool_timeout = _int_env("DB_POOL_TIMEOUT", 30)
    pool_recycle = _int_env("DB_POOL_RECYCLE", 1800)

    # Защита от некорректных значений
    if pool_size < 1:
        pool_size = 1
    if max_overflow < 0:
        max_overflow = 0
    if pool_timeout < 1:
        pool_timeout = 30
    if pool_recycle < 0:
        pool_recycle = 1800

    return {
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "pool_timeout": pool_timeout,
        "pool_recycle": pool_recycle,
    }


def _get_connect_args() -> dict:
    """
    connect_args для asyncpg.

    Переменные окружения:
    - DB_STATEMENT_TIMEOUT_MS (например 30000)
    - DB_APPLICATION_NAME (например mp_seller_bot)
    """
    connect_args: dict = {}

    statement_timeout_ms = os.getenv("DB_STATEMENT_TIMEOUT_MS")
    if statement_timeout_ms is not None and str(statement_timeout_ms).strip():
        try:
            ms = int(str(statement_timeout_ms).strip())
            if ms > 0:
                connect_args.setdefault("server_settings", {})
                connect_args["server_settings"]["statement_timeout"] = str(ms)
        except Exception:
            pass

    app_name = os.getenv("DB_APPLICATION_NAME")
    if app_name is not None and str(app_name).strip():
        connect_args.setdefault("server_settings", {})
        connect_args["server_settings"]["application_name"] = str(app_name).strip()

    return connect_args


def _create_engine() -> AsyncEngine:
    dsn = settings.database_dsn()
    pool_cfg = _get_pool_settings()
    connect_args = _get_connect_args()

    logger.info(
        "Creating async DB engine. pool_size=%s max_overflow=%s pool_timeout=%s pool_recycle=%s echo=%s",
        pool_cfg["pool_size"],
        pool_cfg["max_overflow"],
        pool_cfg["pool_timeout"],
        pool_cfg["pool_recycle"],
        _get_db_echo(),
    )

    return create_async_engine(
        dsn,
        pool_pre_ping=True,
        echo=_get_db_echo(),
        connect_args=connect_args,
        **pool_cfg,
    )


# Создаём асинхронный движок SQLAlchemy. DSN берётся из конфигурации.
engine: AsyncEngine = _create_engine()

# Фабрика асинхронных сессий. expire_on_commit=False исключает автоматическое
# обновление объектов после коммита, что упрощает работу в рамках одной сессии.
SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def db_ping() -> bool:
    """
    Быстрая проверка доступности БД (SELECT 1).
    Возвращает True/False, исключения не пробрасывает.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning("DB ping failed: %s", e)
        return False


async def init_db() -> None:
    """
    Создаёт таблицы в базе данных, если они отсутствуют.

    Импорт моделей находится внутри функции, чтобы избежать циклических
    зависимостей. При использовании Alembic этот метод можно заменить миграциями.

    Дополнительно:
    - перед созданием таблиц выполняется простая проверка соединения
    - логируются ошибки и контекст
    """
    # Импортируем модели для регистрации в metadata.
    # noqa используется для подавления предупреждений линтера о неиспользуемых переменных.
    from .models import MarketplaceCredential, OrderEvent, User  # noqa: F401

    # Проверим соединение
    ok = await db_ping()
    if not ok:
        logger.error("DB is not reachable at startup. Check DSN/credentials/network.")
        # Не падаем жёстко здесь, чтобы в некоторых окружениях можно было увидеть логи,
        # но чаще всего правильнее упасть и перезапуститься (docker/systemd).
        raise RuntimeError("Database is not reachable (db_ping failed).")

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("DB initialized (tables ensured)")
    except SQLAlchemyError as e:
        logger.exception("DB init failed with SQLAlchemyError: %s", e)
        raise
    except Exception as e:
        logger.exception("DB init failed: %s", e)
        raise


async def close_db() -> None:
    """
    Корректно освобождает ресурсы движка SQLAlchemy.
    Вызывать при завершении приложения (если есть явный lifecycle).
    """
    try:
        await engine.dispose()
        logger.info("DB engine disposed")
    except Exception as e:
        logger.warning("Failed to dispose DB engine: %s", e)
