"""
Версия файла: 1.3.0
Описание: Telegram‑хэндлеры с поддержкой многоуровневого меню, FSM и вебхуков
Дата изменения: 2025-12-27

Этот модуль содержит обработчики сообщений для Telegram‑бота. Он
реализует несколько функций:

* Приветствие пользователя и вывод главного меню с разделами («Заказы»,
  «Подключения», «Аналитика», «Подсказки», «Помощь»).
* Управление состояниями FSM при вводе ключей для Wildberries и Ozon
  (Client ID + токен).
* Переходы между подменю (заказы, подключения, аналитика, подсказки).
* Обработка выбора периода заказов: сегодня, вчера, 7 дней, произвольный
  диапазон (запрашивает число дней).
* Вывод аналитики заказов за последние 7 дней.
* Отправка случайных лайфхаков по продажам, если пользователь вводит
  произвольный текст вне сценария.
* Команды /start, /help, /status, /cancel.

Обработчики построены на aiogram 3, используют FSM для последовательного
ввода параметров (например, для Ozon: сначала Client ID, затем токен).
Все сообщения сопровождаются удобными клавиатурами, определёнными в
``bot.keyboards.menu``.
"""

from __future__ import annotations

import logging
import random
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import select

from bot.keyboards.menu import (
    main_menu,
    orders_menu,
    connections_menu,
    analytics_menu,
    tips_menu,
)
from bot.key_store import (
    get_wb_api_key,
    get_ozon_credentials,
    upsert_wb_api_key,
    upsert_ozon_credentials,
)
from config import settings
from db import SessionLocal
from db.models import MarketplaceAccount
from services.analytics_service import AnalyticsService

logger = logging.getLogger("handlers")


class KeyStates(StatesGroup):
    """FSM состояния для ввода ключей Wildberries."""

    waiting_wb_key = State()


class OzonStates(StatesGroup):
    """FSM состояния для ввода данных Ozon (Client ID и токен)."""

    waiting_client_id = State()
    waiting_token = State()


class OrdersStates(StatesGroup):
    """FSM состояние для запроса произвольного периода заказов."""

    waiting_days = State()


# Список полезных лайфхаков/советов по работе с маркетплейсами.
LIFE_HACKS = [
    "Анализируйте выкупы: повышайте рейтинг товара за счёт снижения отмен.",
    "Работайте с отзывами: оперативно отвечайте и улучшайте карточку товара.",
    "Следите за остатками: отсутствие товара на складе равносильно потере продаж.",
    "Используйте рекламные кампании только для топовых SKU — это увеличит отдачу.",
    "Оптимизируйте цены: мониторьте конкурентов и корректируйте стоимость.",
    "Добавляйте подарки или пробники: это увеличивает лояльность клиентов.",
    "Сегментируйте ассортимент: фокусируйтесь на товарах с высоким оборотом.",
    "Используйте акции и распродажи, чтобы привлечь новых покупателей.",
    "Улучшайте фотографии и описание товара — это повышает конверсию.",
    "Проверьте упаковку: она должна защищать товар и выглядеть привлекательно.",
]


def _mask_key(key: str) -> str:
    """Маскирует ключ или Client ID для отображения в статусе."""
    if not key or len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Приветствие и вывод основного меню."""
    await state.clear()
    text = (
        "<b>Добро пожаловать в Seller Bot!</b>\n\n"
        "Этот бот поможет вам отслеживать заказы и продажи на Wildberries и Ozon, \n"
        "а также предоставит аналитику и полезные советы.\n\n"
        "Выберите раздел в меню ниже или воспользуйтесь командами:\n"
        "• /connect_wb — подключить Wildberries\n"
        "• /connect_ozon — подключить Ozon (Client ID + токен)\n"
        "• /status — проверить подключенные аккаунты\n"
        "• /help — справка по использованию бота"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext) -> None:
    """Отображает справочную информацию и основное меню."""
    await state.clear()
    help_text = (
        "<b>Справка по Seller Bot</b>\n\n"
        "Доступные команды:\n"
        "/start — запустить бота и вывести меню\n"
        "/help — показать эту справку\n"
        "/status — статус подключений\n"
        "/cancel — отменить текущее действие\n\n"
        "Разделы меню:\n"
        "• <b>Заказы</b> — получить статистику заказов за выбранный период.\n"
        "• <b>Подключения</b> — подключить или отключить аккаунты WB и Ozon.\n"
        "• <b>Аналитика</b> — быстрый отчёт по заказам за 7 дней.\n"
        "• <b>Подсказки</b> — случайные лайфхаки и советы.\n"
        "• <b>Помощь</b> — эта справка.\n"
    )
    await message.answer(help_text, parse_mode="HTML", reply_markup=main_menu())


@router.message(Command("status"))
async def cmd_status(message: Message, state: FSMContext) -> None:
    """Показывает статус подключений."""
    tg_user_id = message.from_user.id if message.from_user else 0
    if tg_user_id == 0:
        await message.answer("Не удалось определить пользователя Telegram.", reply_markup=main_menu())
        return

    async with SessionLocal() as session:
        wb_key = await get_wb_api_key(session, tg_user_id, settings.fernet_key)
        ozon_creds = await get_ozon_credentials(session, tg_user_id, settings.fernet_key)

    wb_status = f"подключен ({_mask_key(wb_key)})" if wb_key else "не подключен"
    ozon_status = (
        f"подключен (Client ID: {_mask_key(ozon_creds[0])}, Token: {_mask_key(ozon_creds[1])})"
        if ozon_creds
        else "не подключен"
    )

    await message.answer(
        "Статус подключений:\n"
        f"• Wildberries: {wb_status}\n"
        f"• Ozon: {ozon_status}",
        reply_markup=main_menu(),
    )


# === Навигация по меню ===

@router.message(F.text.casefold() == "заказы")
async def show_orders_menu(message: Message, state: FSMContext) -> None:
    """Отображает подменю заказов."""
    await state.clear()
    await message.answer(
        "Выберите период для получения статистики:\n"
        "Сегодня, Вчера, 7 дней или укажите произвольный период.",
        reply_markup=orders_menu(),
    )


@router.message(F.text.casefold() == "подключения")
async def show_connections_menu(message: Message, state: FSMContext) -> None:
    """Отображает подменю подключений."""
    await state.clear()
    await message.answer(
        "Управление подключениями:\n"
        "Вы можете подключить или отключить аккаунты Wildberries и Ozon.",
        reply_markup=connections_menu(),
    )


@router.message(F.text.casefold() == "аналитика")
async def show_analytics_menu(message: Message, state: FSMContext) -> None:
    """Отображает подменю аналитики и сразу выдаёт отчёт за 7 дней."""
    await state.clear()
    tg_user_id = message.from_user.id if message.from_user else 0
    if tg_user_id == 0:
        await message.answer("Не удалось определить пользователя.", reply_markup=main_menu())
        return
    async with SessionLocal() as session:
        service = AnalyticsService(session)
        stats = await service.orders_count_last_days(tg_user_id, days=7)
    lines = ["Статистика заказов за 7 дней:"]
    if not stats:
        lines.append("Нет заказов за этот период.")
    else:
        for key, value in sorted(stats.items()):
            lines.append(f"• {key}: {value}")
    await message.answer("\n".join(lines), reply_markup=analytics_menu())


@router.message(F.text.casefold() == "подсказки")
async def show_tips_menu(message: Message, state: FSMContext) -> None:
    """Отображает раздел подсказок (лайфхаки)."""
    await state.clear()
    tip = random.choice(LIFE_HACKS)
    await message.answer(
        f"<b>Лайфхак:</b> {tip}",
        parse_mode="HTML",
        reply_markup=tips_menu(),
    )


@router.message(F.text.casefold() == "помощь")
async def show_help_button(message: Message, state: FSMContext) -> None:
    """Кнопка «Помощь» отображает справку."""
    await cmd_help(message, state)


# === Обработчики заказов ===

@router.message(F.text.casefold() == "сегодня")
async def orders_today(message: Message, state: FSMContext) -> None:
    """Вывод статистики за сегодня (последние 1 сутки)."""
    tg_user_id = message.from_user.id if message.from_user else 0
    async with SessionLocal() as session:
        service = AnalyticsService(session)
        stats = await service.orders_count_last_days(tg_user_id, days=1)
    lines = ["Статистика заказов за сегодня:"]
    if not stats:
        lines.append("Сегодня заказов нет.")
    else:
        for k, v in sorted(stats.items()):
            lines.append(f"• {k}: {v}")
    await message.answer("\n".join(lines), reply_markup=orders_menu())


@router.message(F.text.casefold() == "вчера")
async def orders_yesterday(message: Message, state: FSMContext) -> None:
    """Вывод статистики за вчера (разница между 2 днями и 1 днём)."""
    tg_user_id = message.from_user.id if message.from_user else 0
    async with SessionLocal() as session:
        service = AnalyticsService(session)
        stats_2 = await service.orders_count_last_days(tg_user_id, days=2)
        stats_1 = await service.orders_count_last_days(tg_user_id, days=1)
    # Вычитаем количество за 1 день, чтобы получить только вчерашний день
    diff: dict[str, int] = {}
    for key, val in stats_2.items():
        prev = stats_1.get(key, 0)
        diff[key] = val - prev
    lines = ["Статистика заказов за вчера:"]
    if not diff:
        lines.append("Вчера заказов не было.")
    else:
        for k, v in sorted(diff.items()):
            lines.append(f"• {k}: {v}")
    await message.answer("\n".join(lines), reply_markup=orders_menu())


@router.message(F.text.casefold() == "7 дней")
async def orders_7days(message: Message, state: FSMContext) -> None:
    """Вывод статистики за последние 7 дней."""
    tg_user_id = message.from_user.id if message.from_user else 0
    async with SessionLocal() as session:
        service = AnalyticsService(session)
        stats = await service.orders_count_last_days(tg_user_id, days=7)
    lines = ["Статистика заказов за 7 дней:"]
    if not stats:
        lines.append("За последние 7 дней заказов нет.")
    else:
        for k, v in sorted(stats.items()):
            lines.append(f"• {k}: {v}")
    await message.answer("\n".join(lines), reply_markup=orders_menu())


@router.message(F.text.casefold() == "период")
async def orders_period(message: Message, state: FSMContext) -> None:
    """Запрашивает число дней для произвольного периода."""
    await state.set_state(OrdersStates.waiting_days)
    await message.answer(
        "Введите количество дней, за которые нужно вывести статистику (например, 14)",
        reply_markup=orders_menu(),
    )


@router.message(OrdersStates.waiting_days)
async def orders_custom_period(message: Message, state: FSMContext) -> None:
    """Обрабатывает ввод количества дней и показывает статистику."""
    text = (message.text or "").strip()
    try:
        days = int(text)
    except ValueError:
        await message.answer("Пожалуйста, введите целое число дней.", reply_markup=orders_menu())
        return
    if days <= 0:
        await message.answer("Количество дней должно быть положительным.", reply_markup=orders_menu())
        return
    tg_user_id = message.from_user.id if message.from_user else 0
    async with SessionLocal() as session:
        service = AnalyticsService(session)
        stats = await service.orders_count_last_days(tg_user_id, days=days)
    lines = [f"Статистика заказов за последние {days} дней:"]
    if not stats:
        lines.append("Нет заказов за выбранный период.")
    else:
        for k, v in sorted(stats.items()):
            lines.append(f"• {k}: {v}")
    await state.clear()
    await message.answer("\n".join(lines), reply_markup=orders_menu())


# === Обработчики подключений ===

@router.message(F.text.casefold() == "подключить wildberries")
@router.message(Command("connect_wb"))
async def btn_connect_wb(message: Message, state: FSMContext) -> None:
    """Запрашивает API ключ Wildberries."""
    await state.set_state(KeyStates.waiting_wb_key)
    await message.answer(
        "Отправьте API ключ Wildberries одним сообщением.\n"
        "Ключ будет сохранён в зашифрованном виде.\n\n"
        "Чтобы отменить — введите /cancel",
        reply_markup=connections_menu(),
    )


@router.message(KeyStates.waiting_wb_key)
async def process_wb_key(message: Message, state: FSMContext) -> None:
    """Сохраняет ключ WB и удаляет сообщение пользователя."""
    tg_user_id = message.from_user.id if message.from_user else 0
    api_key = (message.text or "").strip()
    async with SessionLocal() as session:
        await upsert_wb_api_key(session, tg_user_id, api_key, settings.fernet_key)
    try:
        await message.delete()
    except Exception:
        pass
    await state.clear()
    await message.answer(
        "Ключ Wildberries сохранён и скрыт. Мониторинг включён.",
        reply_markup=connections_menu(),
    )


@router.message(F.text.casefold() == "подключить ozon")
@router.message(Command("connect_ozon"))
async def btn_connect_ozon(message: Message, state: FSMContext) -> None:
    """Начинает последовательный ввод Client ID и токена Ozon."""
    await state.set_state(OzonStates.waiting_client_id)
    await message.answer(
        "Введите Client ID Ozon. После этого я попрошу токен.\n\n"
        "Чтобы отменить — введите /cancel",
        reply_markup=connections_menu(),
    )


@router.message(OzonStates.waiting_client_id)
async def process_ozon_client_id(message: Message, state: FSMContext) -> None:
    """Сохраняет введённый Client ID во временное состояние и просит токен."""
    client_id = (message.text or "").strip()
    if not client_id:
        await message.answer("Client ID не должен быть пустым.", reply_markup=connections_menu())
        return
    await state.update_data(client_id=client_id)
    await state.set_state(OzonStates.waiting_token)
    await message.answer("Теперь отправьте токен Ozon одним сообщением.", reply_markup=connections_menu())


@router.message(OzonStates.waiting_token)
async def process_ozon_token(message: Message, state: FSMContext) -> None:
    """Сохраняет Client ID и токен Ozon в БД, удаляет сообщение."""
    data = await state.get_data()
    client_id = data.get("client_id")
    token = (message.text or "").strip()
    if not token:
        await message.answer("Токен не должен быть пустым.", reply_markup=connections_menu())
        return
    tg_user_id = message.from_user.id if message.from_user else 0
    async with SessionLocal() as session:
        await upsert_ozon_credentials(session, tg_user_id, client_id, token, settings.fernet_key)
    try:
        await message.delete()
    except Exception:
        pass
    await state.clear()
    await message.answer(
        "Client ID и токен Ozon сохранены и скрыты. Мониторинг включён.",
        reply_markup=connections_menu(),
    )


@router.message(F.text.casefold() == "отключить wb")
async def btn_disable_wb(message: Message, state: FSMContext) -> None:
    """Деактивирует аккаунт Wildberries."""
    tg_user_id = message.from_user.id if message.from_user else 0
    async with SessionLocal() as session:
        q = select(MarketplaceAccount).where(
            MarketplaceAccount.tg_user_id == tg_user_id,
            MarketplaceAccount.marketplace == "wb",
        )
        res = await session.execute(q)
        acc = res.scalar_one_or_none()
        if acc:
            acc.is_active = False
            await session.commit()
    await message.answer("Wildberries отключён.", reply_markup=connections_menu())


@router.message(F.text.casefold() == "отключить ozon")
async def btn_disable_ozon(message: Message, state: FSMContext) -> None:
    """Деактивирует аккаунт Ozon."""
    tg_user_id = message.from_user.id if message.from_user else 0
    async with SessionLocal() as session:
        q = select(MarketplaceAccount).where(
            MarketplaceAccount.tg_user_id == tg_user_id,
            MarketplaceAccount.marketplace == "ozon",
        )
        res = await session.execute(q)
        acc = res.scalar_one_or_none()
        if acc:
            acc.is_active = False
            await session.commit()
    await message.answer("Ozon отключён.", reply_markup=connections_menu())


# === Дополнительные обработчики ===

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Отменяет любое текущее состояние и возвращает меню."""
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu())


@router.message(F.text.casefold() == "назад в меню")
async def menu_back(message: Message, state: FSMContext) -> None:
    """Возвращает пользователя в основное меню."""
    await state.clear()
    await message.answer("Главное меню:", reply_markup=main_menu())


@router.message(F.text.casefold() == "аналитика 7 дней")
async def analytics_7days_button(message: Message, state: FSMContext) -> None:
    """Кнопка из подменю аналитики: выводит статистику за 7 дней."""
    await show_analytics_menu(message, state)


@router.message(F.text.casefold() == "получить лайфхак")
async def get_another_tip(message: Message, state: FSMContext) -> None:
    """Кнопка из раздела подсказок: отправляет ещё один случайный совет."""
    tip = random.choice(LIFE_HACKS)
    await message.answer(f"<b>Лайфхак:</b> {tip}", parse_mode="HTML", reply_markup=tips_menu())


# === Fallback ===

@router.message()
async def fallback(message: Message, state: FSMContext) -> None:
    """Обработчик для всех прочих сообщений: случайный лайфхак и меню."""
    # Если есть активное состояние FSM (например, ожидание ключа), не перехватываем
    current_state = await state.get_state()
    if current_state:
        return
    tip = random.choice(LIFE_HACKS)
    await message.answer(
        f"Я не понял запрос. Вот вам полезный лайфхак:\n\n<b>{tip}</b>",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )