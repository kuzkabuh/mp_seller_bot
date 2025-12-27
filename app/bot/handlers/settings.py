"""
Версия файла: 1.0.0
Описание: Настройки/служебные обработчики для mp_seller_bot
Дата изменения: 2025-12-27
"""

from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

router = Router()


@router.message()
async def fallback(message: Message) -> None:
    await message.answer("Не понял команду. Нажмите «Помощь» или используйте кнопки меню.")
