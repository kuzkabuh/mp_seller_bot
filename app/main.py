"""
Версия файла: 1.0.0
Описание: Точка входа mp_seller_bot (aiogram + фоновые воркеры)
Дата изменения: 2025-12-27
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from bot.dispatcher import build_dispatcher
from config import settings
from db.engine import engine
from db.models import Base
from logging_setup import setup_logging
from workers.notifier import worker_loop

logger = logging.getLogger("main")


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main() -> None:
    setup_logging(settings.LOG_LEVEL)
    logger.info("Starting mp_seller_bot...")

    await init_db()

    bot = Bot(token=settings.BOT_TOKEN)
    dp = build_dispatcher()

    worker_task = asyncio.create_task(worker_loop(bot))

    try:
        await dp.start_polling(bot)
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
