# main.py
# Версия файла: 1.1.4
# Описание: Главный файл Telegram-бота mp_seller_bot (polling/webhook, health, graceful shutdown, воркер уведомлений)
# Дата изменения: 2025-12-28

from __future__ import annotations

import asyncio
import logging
import os
import signal
from typing import Optional

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import settings
from db import init_db
from logging_config import setup_logging
from bot.handlers import router as main_router
from workers.notifier import worker_loop

logger = logging.getLogger("main")


def _bool_env(val: Optional[str]) -> bool:
    if val is None:
        return False
    return val.strip().lower() in ("1", "true", "yes", "y", "on")


def _get_webhook_secret() -> str:
    # WEBHOOK_SECRET: секрет в URL. Лучше длиной 32+ символа.
    v = getattr(settings, "WEBHOOK_SECRET", None) or os.getenv("WEBHOOK_SECRET", "")
    v = (v or "").strip()
    return v


def _get_webhook_base_url() -> str:
    # Например: https://mpsellerbot.kuzkabuh.ru
    v = getattr(settings, "WEBHOOK_BASE_URL", None) or os.getenv("WEBHOOK_BASE_URL", "")
    return (v or "").strip().rstrip("/")


def _get_webhook_path() -> str:
    # Если секрет задан — используем /webhook/<secret>, иначе /webhook (не рекомендуется)
    secret = _get_webhook_secret()
    if secret:
        return f"/webhook/{secret}"
    return "/webhook"


def _get_webhook_listen_host() -> str:
    return (getattr(settings, "WEBHOOK_LISTEN_HOST", None) or os.getenv("WEBHOOK_LISTEN_HOST") or "0.0.0.0").strip()


def _get_webhook_listen_port() -> int:
    raw = getattr(settings, "WEBHOOK_LISTEN_PORT", None) or os.getenv("WEBHOOK_LISTEN_PORT") or "8000"
    try:
        return int(str(raw).strip())
    except Exception:
        return 8000


def _webhook_enabled() -> bool:
    # Авто-режим:
    # - Если WEBHOOK_BASE_URL задан → включаем webhook
    # - Или если WEBHOOK_ENABLED=1 → включаем webhook
    base = _get_webhook_base_url()
    flag = getattr(settings, "WEBHOOK_ENABLED", None)
    if flag is None:
        flag = os.getenv("WEBHOOK_ENABLED")
    return bool(base) or _bool_env(str(flag) if flag is not None else None)


def _get_bot_token() -> str:
    """
    Получает токен бота из настроек или окружения.

    Приоритет:
    1. settings.BOT_TOKEN
    2. settings.bot_token
    3. переменная окружения BOT_TOKEN
    4. переменная окружения TELEGRAM_BOT_TOKEN

    Если ни один вариант не найден — поднимает RuntimeError
    с понятным сообщением.
    """
    token = getattr(settings, "BOT_TOKEN", None)
    if not token:
        token = getattr(settings, "bot_token", None)

    if not token:
        token = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        logger.error(
            "Не задан токен бота. Установите переменную окружения BOT_TOKEN "
            "или TELEGRAM_BOT_TOKEN, либо поле bot_token / BOT_TOKEN в Settings."
        )
        raise RuntimeError(
            "BOT_TOKEN (токен Telegram-бота) не найден в настройках. "
            "Проверьте .env и конфигурацию Settings."
        )

    return token.strip()


def _validate_webhook_settings() -> None:
    """
    Мягкая валидация webhook-настроек (без падения),
    чтобы избежать типичных ошибок при деплое.
    """
    if not _webhook_enabled():
        return

    base_url = _get_webhook_base_url()
    secret = _get_webhook_secret()

    if not base_url:
        logger.warning("WEBHOOK_BASE_URL пустой. Webhook-режим включен, но webhook не будет установлен.")
        return

    if not (base_url.startswith("https://") or base_url.startswith("http://")):
        logger.warning("WEBHOOK_BASE_URL должен начинаться с http:// или https://. Сейчас: %s", base_url)

    if base_url.startswith("http://"):
        logger.warning("WEBHOOK_BASE_URL использует http://. Для Telegram webhook рекомендуется https://.")

    if not secret:
        logger.warning(
            "WEBHOOK_SECRET не задан. Будет использован путь /webhook без секрета. "
            "Это небезопасно — задайте WEBHOOK_SECRET длиной 32+ символа."
        )
    elif len(secret) < 32:
        logger.warning(
            "WEBHOOK_SECRET слишком короткий (%s). Рекомендуется 32+ символа.",
            len(secret),
        )


async def health_handler(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def on_startup(bot: Bot) -> None:
    """
    Важно: aiogram передает bot в startup, если мы передали bot=bot в setup_application.
    """
    mode = "webhook" if _webhook_enabled() else "polling"
    logger.info("Bot startup. mode=%s", mode)

    if _webhook_enabled():
        base_url = _get_webhook_base_url()
        path = _get_webhook_path()
        if not base_url:
            logger.warning("WEBHOOK_BASE_URL is empty. Webhook cannot be set.")
            return

        webhook_url = f"{base_url}{path}"
        try:
            await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
            logger.info("Webhook set: %s", webhook_url)
        except Exception:
            logger.exception("Failed to set webhook")


async def on_shutdown(bot: Bot) -> None:
    # В webhook-режиме корректно снимаем webhook
    if _webhook_enabled():
        try:
            await bot.delete_webhook(drop_pending_updates=False)
            logger.info("Webhook deleted")
        except Exception:
            logger.exception("Failed to delete webhook")


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    """
    Корректная остановка по SIGINT/SIGTERM:
    - в Docker SIGTERM приходит при `docker stop`
    - локально SIGINT при Ctrl+C
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    def _request_stop() -> None:
        if not stop_event.is_set():
            stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except (NotImplementedError, RuntimeError):
            # NotImplementedError: например, Windows
            # RuntimeError: если loop не поддерживает обработчики
            pass


async def run_webhook(bot: Bot, dp: Dispatcher) -> None:
    """
    Запуск aiohttp сервера для webhook + /health.
    Остановка через stop_event (SIGINT/SIGTERM) или отмену задачи.
    """
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)

    app = web.Application()

    # /health
    app.router.add_get("/health", health_handler)

    # webhook handler
    path = _get_webhook_path()
    request_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    request_handler.register(app, path=path)

    # ВАЖНО: bot передаем ИМЕННО как keyword-arg, чтобы startup/shutdown получали bot
    setup_application(app, dp, bot=bot)

    host = _get_webhook_listen_host()
    port = _get_webhook_listen_port()
    logger.info("Starting webhook server on %s:%s path=%s", host, port, path)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)

    try:
        await site.start()
        await stop_event.wait()
        logger.info("Stop signal received. Shutting down webhook server...")
    except asyncio.CancelledError:
        logger.info("Webhook server task cancelled. Shutting down...")
        raise
    finally:
        try:
            await runner.cleanup()
        except Exception:
            logger.exception("Failed to cleanup aiohttp runner")


async def run_polling(bot: Bot, dp: Dispatcher) -> None:
    """
    Polling режим, если webhook не включен.
    """
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        logger.exception("Failed to delete webhook in polling mode")

    logger.info("Starting polling...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


async def _shutdown_worker(task: asyncio.Task) -> None:
    if task.done():
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Notifier worker failed during shutdown")


async def main() -> None:
    setup_logging()
    logger.info("Starting mp_seller_bot...")

    _validate_webhook_settings()

    await init_db()

    dp = Dispatcher()
    dp.include_router(main_router)

    # регистрируем startup/shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    token = _get_bot_token()

    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # воркер уведомлений (новые заказы и т.п.)
    worker_task = asyncio.create_task(worker_loop(bot), name="notifier_worker")

    try:
        if _webhook_enabled():
            await run_webhook(bot, dp)
        else:
            await run_polling(bot, dp)
    finally:
        await _shutdown_worker(worker_task)
        try:
            await bot.session.close()
        except Exception:
            logger.exception("Failed to close bot session")


if __name__ == "__main__":
    asyncio.run(main())
