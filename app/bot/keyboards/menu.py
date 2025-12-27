"""
Версия файла: 1.0.0
Описание: Клавиатуры меню для mp_seller_bot
Дата изменения: 2025-12-27
"""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Подключить Wildberries"), KeyboardButton(text="Подключить Ozon")],
            [KeyboardButton(text="Аналитика за 7 дней"), KeyboardButton(text="Подсказки по выручке")],
            [KeyboardButton(text="Отключить WB"), KeyboardButton(text="Отключить Ozon")],
            [KeyboardButton(text="Помощь")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие…",
    )
