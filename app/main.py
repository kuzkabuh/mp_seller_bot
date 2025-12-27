"""
Версия файла: 1.3.0
Описание: Точка входа приложения. Поддержка webhook и polling + /health.
Дата изменения: 2025-12-27

Что делает:
- Инициализирует логирование и БД
- Запускает Telegram-бота (aiogram)
- В режиме webhook поднимает aiohttp-сервер:
  - принимает Telegram webhook по пути settings.webhook_path
  - отдаёт /health (для мониторинга / балансировщика)
- В режиме polling запускает start_polling
- Запускает фоновый воркер уведомлений
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from bot.handlers import router as bot_router
from config import settings
from db import init_db
from logging_config import setup_logging
from workers.notifier import worker_loop

logger = logging.getLogger("main")


async def health_handler(request: web.Request) -> web.Response:
    """
    Healthcheck endpoint.
    Возвращает 200 OK, если процесс жив и веб-сервер поднят.
    """
    payload: dict[str, Any] = {
        "status": "ok",
        "service": "mp_seller_bot",
        "mode": "webhook" if settings.use_webhook else "polling",
    }
    return web.json_response(payload, status=200)


async def on_startup(bot: Bot) -> None:
    """
    При webhook-режиме регистрируем webhook в Telegram.
    """
    if not settings.base_webhook_url:
        logger.warning("BASE_WEBHOOK_URL не указан — webhook не будет установлен.")
        return

    url = settings.base_webhook_url.rstrip("/") + settings.webhook_path
    await bot.set_webhook(url=url, secret_token=settings.webhook_secret)
    logger.info("Webhook registered: %s", url)


async def on_shutdown(bot: Bot) -> None:
    """
    Корректное выключение: снимаем webhook и закрываем сессию бота.
    """
    if settings.use_webhook:
        with suppress(Exception):
            await bot.delete_webhook(drop_pending_updates=False)

    with suppress(Exception):
        await bot.session.close()


async def run_webhook(bot: Bot, dp: Dispatcher) -> None:
    """
    Запуск aiohttp сервера для webhook.
    Используем AppRunner/TCPSite, чтобы оставаться в async-контексте.
    """
    app = web.Application()

    # /health
    app.router.add_get("/health", health_handler)

    # Telegram webhook handler
    handler = SimpleRequestHandler(dp, bot, secret_token=settings.webhook_secret)
    handler.register(app, path=settings.webhook_path)

    # ВАЖНО: setup_application(app, dp) — в aiogram 3.x именно так
    setup_application(app, dp)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(
        runner,
        host=settings.webhook_host or "0.0.0.0",
        port=settings.webhook_port,
    )

    logger.info(
        "Webhook server started: http://%s:%s%s (health: /health)",
        settings.webhook_host or "0.0.0.0",
        settings.webhook_port,
        settings.webhook_path,
    )

    await site.start()

    # Держим процесс живым
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        with suppress(Exception):
            await runner.cleanup()


async def main() -> None:
    setup_logging(settings.log_level)
    logger.info("Starting mp_seller_bot...")

    await init_db()

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(bot_router)

    # В webhook-режиме регистрируем хуки
    if settings.use_webhook:
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

    # Фоновый воркер уведомлений
    worker_task = asyncio.create_task(worker_loop(bot))

    try:
        if settings.use_webhook:
            await run_webhook(bot, dp)
        else:
            logger.info("Starting polling mode")
            await dp.start_polling(bot)
    finally:
        worker_task.cancel()
        with suppress(Exception):
            await worker_task
        with suppress(Exception):
            await on_shutdown(bot)


if __name__ == "__main__":
    asyncio.run(main())
