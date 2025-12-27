# Версия файла: 1.2.0
# Описание: Хэндлеры Telegram-бота (добавлена FSM для Ozon: client_id + token)
# Дата изменения: 2025-12-27

from __future__ import annotations

import logging
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.keyboards.menu import main_menu
from bot.key_store import (
    get_ozon_credentials,
    get_wb_api_key,
    upsert_ozon_credentials,
    upsert_wb_api_key,
)
from config import settings
from db import SessionLocal

logger = logging.getLogger("handlers")

router = Router()


class OzonStates(StatesGroup):
    waiting_client_id = State()
    waiting_token = State()


def _mask_key(key: str) -> str:
    if len(key) <= 10:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    text = (
        "<b>Seller Bot</b> — уведомления и аналитика для WB / Ozon\n\n"
        "Выберите действие кнопками или используйте команды:\n"
        "• /connect_wb — подключить Wildberries\n"
        "• /connect_ozon — подключить Ozon\n"
        "• /status — статус подключений\n"
        "• /help — помощь"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Поддерживаемые действия:\n"
        "• Подключить Wildberries — сохранить API ключ WB\n"
        "• Подключить Ozon — сохранить Client ID и API ключ Ozon\n"
        "• Отключить WB / Ozon — остановить мониторинг\n"
        "• Статус — вывести список подключённых аккаунтов\n"
        "• В будущем появятся уведомления о заказах и аналитика",
        reply_markup=main_menu(),
    )


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
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


# === Обработчики для кнопок ===

@router.message(F.text.casefold() == "подключить wildberries")
@router.message(Command("connect_wb"))
async def btn_connect_wb(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Отправьте API ключ Wildberries одним сообщением.\n"
        "Ключ будет сохранён в зашифрованном виде.\n\n"
        "Чтобы отменить — отправьте /cancel",
        reply_markup=main_menu(),
    )
    await state.set_state("waiting_wb_key")


@router.message(F.text.casefold() == "подключить ozon")
@router.message(Command("connect_ozon"))
async def btn_connect_ozon(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Введите Client ID Ozon.\n"
        "После этого я попрошу токен.\n\n"
        "Чтобы отменить — отправьте /cancel",
        reply_markup=main_menu(),
    )
    await state.set_state(OzonStates.waiting_client_id)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu())


@router.message(F.text.casefold() == "отключить wb")
async def btn_disable_wb(message: Message) -> None:
    # деактивируем в базе
    tg_user_id = message.from_user.id if message.from_user else 0
    async with SessionLocal() as session:
        q = (
            select(MarketplaceAccount)
            .where(
                MarketplaceAccount.tg_user_id == tg_user_id,
                MarketplaceAccount.marketplace == "wb",
            )
        )
        res = await session.execute(q)
        row = res.scalar_one_or_none()
        if row:
            row.is_active = False
            await session.commit()
    await message.answer("Wildberries отключён.", reply_markup=main_menu())


@router.message(F.text.casefold() == "отключить ozon")
async def btn_disable_ozon(message: Message) -> None:
    tg_user_id = message.from_user.id if message.from_user else 0
    async with SessionLocal() as session:
        q = (
            select(MarketplaceAccount)
            .where(
                MarketplaceAccount.tg_user_id == tg_user_id,
                MarketplaceAccount.marketplace == "ozon",
            )
        )
        res = await session.execute(q)
        row = res.scalar_one_or_none()
        if row:
            row.is_active = False
            await session.commit()
    await message.answer("Ozon отключён.", reply_markup=main_menu())


# === Состояния для записи ключей ===

@router.message(FSMContext.state == "waiting_wb_key")
async def process_wb_key(message: Message, state: FSMContext) -> None:
    tg_user_id = message.from_user.id if message.from_user else 0
    api_key = (message.text or "").strip()
    # Сохраняем и удаляем сообщение
    async with SessionLocal() as session:
        await upsert_wb_api_key(session, tg_user_id, api_key, settings.fernet_key)
    try:
        await message.delete()
    except Exception:
        pass
    await state.clear()
    await message.answer(
        "Ключ Wildberries сохранён и скрыт. Мониторинг будет работать автоматически.",
        reply_markup=main_menu(),
    )


@router.message(OzonStates.waiting_client_id)
async def process_ozon_client_id(message: Message, state: FSMContext) -> None:
    client_id = (message.text or "").strip()
    if not client_id:
        await message.answer("Client ID не должен быть пустым. Попробуйте ещё раз.", reply_markup=main_menu())
        return
    await state.update_data(client_id=client_id)
    await state.set_state(OzonStates.waiting_token)
    await message.answer("Теперь отправьте токен Ozon одним сообщением.", reply_markup=main_menu())


@router.message(OzonStates.waiting_token)
async def process_ozon_token(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    client_id = data.get("client_id")
    token = (message.text or "").strip()
    if not token:
        await message.answer("Токен не должен быть пустым. Попробуйте ещё раз.", reply_markup=main_menu())
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
        "Клиент и токен Ozon сохранены и скрыты. Мониторинг будет работать автоматически.",
        reply_markup=main_menu(),
    )
