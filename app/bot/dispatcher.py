"""
Версия файла: 1.0.0
Описание: Инициализация роутеров и диспетчера aiogram для mp_seller_bot
Дата изменения: 2025-12-27
"""

from __future__ import annotations

from aiogram import Dispatcher

from bot.handlers.start import router as start_router
from bot.handlers.keys import router as keys_router
from bot.handlers.analytics import router as analytics_router
from bot.handlers.settings import router as settings_router


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(start_router)
    dp.include_router(keys_router)
    dp.include_router(analytics_router)
    dp.include_router(settings_router)
    return dp
