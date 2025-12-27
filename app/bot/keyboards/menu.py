"""
Версия файла: 2.0.0
Описание: Набор клавиатур для основного и вложенных меню бота.
Дата изменения: 2025-12-27

В этом модуле определены несколько функций, возвращающих различные
варианты клавиатур, которые используются для организации многоуровневого
меню в Telegram‑боте. Основное меню содержит категории, такие как
«Заказы», «Подключения», «Аналитика», «Подсказки» и «Помощь». Для каждой
категории есть собственное подменю с более детальными кнопками.

Функции:

- main_menu(): возвращает клавиатуру основного меню.
- orders_menu(): клавиатура раздела «Заказы» с периодами.
- connections_menu(): клавиатура для управления подключениями.
- analytics_menu(): клавиатура раздела «Аналитика».
- tips_menu(): клавиатура для раздела «Подсказки» (лайфхаки).

Все клавиатуры используют ReplyKeyboardMarkup с resize=True для удобства
на мобильных устройствах и имеют кнопку «Назад в меню» для возврата.
"""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu() -> ReplyKeyboardMarkup:
    """Основное меню с категориями.

    Возвращает клавиатуру, содержащую основные разделы бота. Пользователь
    может выбрать категорию, чтобы перейти в соответствующее подменю.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Заказы"), KeyboardButton(text="Подключения")],
            [KeyboardButton(text="Аналитика"), KeyboardButton(text="Подсказки")],
            [KeyboardButton(text="Помощь")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел…",
    )


def orders_menu() -> ReplyKeyboardMarkup:
    """Подменю раздела «Заказы».

    Кнопки позволяют выбрать период, за который нужно получить статистику
    по заказам: сегодня, вчера, последние 7 дней или произвольный период.
    Кнопка «Назад в меню» возвращает пользователя к основному меню.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Сегодня"), KeyboardButton(text="Вчера")],
            [KeyboardButton(text="7 дней"), KeyboardButton(text="Период")],
            [KeyboardButton(text="Назад в меню")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите период заказов…",
    )


def connections_menu() -> ReplyKeyboardMarkup:
    """Подменю управления подключениями к маркетплейсам.

    Здесь можно подключить или отключить Wildberries или Ozon. Кнопка
    «Назад в меню» возвращает к основному меню.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Подключить Wildberries"), KeyboardButton(text="Подключить Ozon")],
            [KeyboardButton(text="Отключить WB"), KeyboardButton(text="Отключить Ozon")],
            [KeyboardButton(text="Назад в меню")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Настройка подключений…",
    )


def analytics_menu() -> ReplyKeyboardMarkup:
    """Подменю раздела «Аналитика».

    В данный момент предусмотрена одна кнопка для быстрой статистики по
    заказам за 7 дней. Кнопка «Назад в меню» возвращает к основному меню.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Аналитика 7 дней")],
            [KeyboardButton(text="Назад в меню")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите тип аналитики…",
    )


def tips_menu() -> ReplyKeyboardMarkup:
    """Подменю для раздела «Подсказки».

    Пользователь может запросить ещё один лайфхак или вернуться в
    основное меню.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Получить лайфхак")],
            [KeyboardButton(text="Назад в меню")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Получить новую подсказку или вернуться…",
    )