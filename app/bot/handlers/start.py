"""
Версия файла: 1.0.0
Описание: /start и помощь для mp_seller_bot
Дата изменения: 2025-12-27

Этот модуль реализует обработчики для команды /start и раздела «Помощь».
Он использует отдельную клавиатуру из ``bot.keyboards.menu`` и просто
отправляет приветственное сообщение или справочную информацию. Эти
обработчики регистрируются в диспетчере в файле ``bot/dispatcher.py``.
"""

from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards.menu import main_menu

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Приветственное сообщение для команды /start."""
    text = (
        "SellerBot: уведомления и аналитика заказов WB/Ozon.\n\n"
        "Что умею сейчас:\n"
        "1) Сохранить ключи WB/Ozon (в БД, в зашифрованном виде)\n"
        "2) Запуск фоновой проверки новых заказов (скелет, далее подключим реальные API)\n"
        "3) Показать базовую аналитику и подсказки\n\n"
        "Выберите действие кнопками ниже."
    )
    await message.answer(text, reply_markup=main_menu())


@router.message(F.text == "Помощь")
async def help_btn(message: Message) -> None:
    """Отображает список команд и назначение кнопок."""
    text = (
        "Команды:\n"
        "/start — запуск\n\n"
        "Кнопки:\n"
        "Подключить Wildberries — сохранить API ключ WB\n"
        "Подключить Ozon — сохранить API ключ Ozon\n"
        "Аналитика за 7 дней — агрегаты по событиям\n"
        "Подсказки по выручке — рекомендации (черновик)\n"
        "Отключить WB/Ozon — выключить мониторинг"
    )
    await message.answer(text, reply_markup=main_menu())