"""
Версия файла: 1.0.0
Описание: Настройки/служебные обработчики для mp_seller_bot
Дата изменения: 2025-12-27

Этот модуль содержит fallback‑обработчик. Если ни один из
зарегистрированных обработчиков не сработал, бот отправит
сообщение с подсказкой обратиться к меню или помощи.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

router = Router()


@router.message()
async def fallback(message: Message) -> None:
    """Отправляет сообщение по умолчанию, если команда не распознана."""
    await message.answer("Не понял команду. Нажмите «Помощь» или используйте кнопки меню.")