"""
Версия файла: 1.1.0
Описание: /start, помощь и базовая навигация для mp_seller_bot (меню, возврат, безопасные подсказки).
Дата изменения: 2025-12-28

Этот модуль реализует обработчики для команды /start и раздела «Помощь».
Он использует клавиатуры из `bot.keyboards.menu` и отправляет приветственное
сообщение, справочную информацию и базовую навигацию.

Улучшения:
- Добавлен обработчик кнопки "Назад в меню" (единый возврат).
- Добавлен обработчик команды /help (кроме кнопки "Помощь").
- Текст справки приведён к актуальным названиям кнопок и сценариям меню.
- Аккуратные формулировки по безопасности токенов (не показываем токены в ответах).
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.keyboards.menu import (
    BTN_BACK_TO_MENU,
    BTN_HELP,
    main_menu,
)

router = Router()


def _welcome_text() -> str:
    return (
        "mp_seller_bot: уведомления и аналитика для Wildberries и Ozon.\n\n"
        "Что умею сейчас:\n"
        "1) Подключения WB/Ozon: сохранение API-ключей в БД в зашифрованном виде\n"
        "2) Мониторинг (воркер): каркас уведомлений о событиях (далее подключим реальные API)\n"
        "3) Меню: Заказы / Подключения / Аналитика / Подсказки / Помощь\n\n"
        "Безопасность:\n"
        "- Я никогда не показываю ваш токен в ответах.\n"
        "- При вводе токена попробую удалить ваше сообщение (если Telegram позволит).\n"
        "  Если удаление запрещено, честно попрошу удалить сообщение вручную.\n\n"
        "Выберите действие кнопками ниже."
    )


def _help_text() -> str:
    return (
        "Помощь по mp_seller_bot\n\n"
        "Команды:\n"
        "/start — запуск и главное меню\n"
        "/help — справка\n\n"
        "Кнопки главного меню:\n"
        "Заказы — выбор периода → выбор маркетплейса → действия/детали\n"
        "Подключения — подключить/отключить Wildberries и Ozon\n"
        "Аналитика — агрегаты (выручка/продажи/остатки/комиссии) и выбор периода\n"
        "Подсказки — быстрый лайфхак или лайфхак по вашему тексту\n"
        "Помощь — эта справка\n\n"
        "Навигация:\n"
        f"{BTN_BACK_TO_MENU} — вернуться в главное меню\n\n"
        "Если что-то не работает:\n"
        "- Проверьте, что бот запущен и есть доступ к базе данных.\n"
        "- Проверьте переменные окружения (.env): BOT_TOKEN, FERNET_KEY, POSTGRES_*.\n"
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Приветственное сообщение для команды /start."""
    await message.answer(_welcome_text(), reply_markup=main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Справка по командам и кнопкам."""
    await message.answer(_help_text(), reply_markup=main_menu())


@router.message(F.text == BTN_HELP)
async def help_btn(message: Message) -> None:
    """Отображает список команд и назначение кнопок."""
    await message.answer(_help_text(), reply_markup=main_menu())


@router.message(F.text == BTN_BACK_TO_MENU)
async def back_to_menu(message: Message) -> None:
    """Единый возврат в главное меню."""
    await message.answer("Главное меню.", reply_markup=main_menu())


"""
Какой файл прислать следующим (по логике новых функций):

Чтобы реализовать:
1) полноценное меню "Заказы → периоды → выбор МП → детали" (FSM),
2) "лайфхаки" на любой текст,
3) безопасный ввод токена с попыткой удалить сообщение,

пришли, пожалуйста, следующий файл:

- bot/handlers/menu.py или bot/handlers/router.py (тот, где собраны обработчики кнопок меню),
и/или
- bot/handlers/connections.py (если там реализуется ввод токенов WB/Ozon).

Если нет отдельного файла — пришли `bot/handlers/__init__.py` и список файлов в папке handlers,
чтобы я точно попал в нужный модуль.
"""
