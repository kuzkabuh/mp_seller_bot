# Версия файла: 1.1.0
# Описание: Точка входа mp_seller_bot (инициализация логов, БД, Telegram)
# Дата изменения: 2025-12-27

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import settings
from db import init_db
from logging_config import setup_logging
from bot.handlers import router as main_router

logger = logging.getLogger("main")


async def main() -> None:
    setup_logging(settings.log_level)

    logger.info("Starting mp_seller_bot...")

    # Проверим, что ключ шифрования задан
    if not settings.fernet_key or len(settings.fernet_key.strip()) < 10:
        raise RuntimeError("FERNET_KEY не задан или слишком короткий. Укажите корректный ключ в .env")

    await init_db()

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(main_router)

    logger.info("Bot started. Polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
