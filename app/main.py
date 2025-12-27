"""
Версия файла: 1.2.0
Описание: Точка входа приложения. Поддержка webhook и polling.
Дата изменения: 2025-12-27

Этот модуль инициализирует логирование, базу данных, Telegram‑бота и
диспетчер aiogram. В зависимости от конфигурации (USE_WEBHOOK) бот
запускается либо в режиме polling, либо в режиме webhook через aiohttp.
Также запускается фоновый воркер, который проверяет новые заказы и
отправляет уведомления пользователям.
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp.web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import settings
from db import init_db
from logging_config import setup_logging
from bot.handlers import router as bot_router
from workers.notifier import worker_loop

from aiohttp import web

logger = logging.getLogger("main")


async def on_startup(bot: Bot) -> None:
    """Регистрация webhook при запуске приложения."""
    # При использовании webhook необходимо зарегистрировать URL в Telegram
    if settings.base_webhook_url:
        await bot.set_webhook(
            url=settings.base_webhook_url.rstrip("/") + settings.webhook_path,
            secret_token=settings.webhook_secret,
        )
        logger.info("Webhook registered: %s", settings.base_webhook_url + settings.webhook_path)
    else:
        logger.warning("BASE_WEBHOOK_URL не указан, webhook не будет установлен.")


async def main() -> None:
    """Основная корутина приложения."""
    # Настройка логирования
    setup_logging(settings.log_level)
    logger.info("Starting mp_seller_bot...")

    # Инициализация базы данных
    await init_db()

    # Инициализируем бота и диспетчер
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(bot_router)

    # Запускаем фоновый воркер для уведомлений
    worker_task = asyncio.create_task(worker_loop(bot))

    if settings.use_webhook:
        # Режим webhook
        logger.info(
            "Starting webhook server on %s:%s path=%s",
            settings.webhook_host or "0.0.0.0",
            settings.webhook_port,
            settings.webhook_path,
        )
        # Регистрируем хук при старте диспетчера
        dp.startup.register(on_startup)
        app = aiohttp.web.Application()

        async def health_handler(request):
            return web.Response(text="OK")

        app.router.add_get("/health", health_handler)
        
        # Создаём обработчик запросов
        handler = SimpleRequestHandler(dp, bot, secret_token=settings.webhook_secret)
        handler.register(app, path=settings.webhook_path)
        # Важно: назначить функции запуска/остановки aiogram
        setup_application(app, dp, bot)
        # Запускаем aiohttp приложение
        try:
            # Запускаем aiohttp приложение. Используем run_app для корректной работы сигнала.
            await aiohttp.web.run_app(
                app,
                host=settings.webhook_host or "0.0.0.0",
                port=settings.webhook_port,
            )
        finally:
            # При остановке сервера отменяем воркер и ждём его завершения
            worker_task.cancel()
            try:
                await worker_task
            except Exception:
                pass
    else:
        # Режим polling
        logger.info("Starting polling mode")
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