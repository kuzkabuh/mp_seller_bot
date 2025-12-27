"""
Версия файла: 1.0.1
Описание: Подключение/отключение ключей WB/Ozon для mp_seller_bot
Дата изменения: 2025-12-27
"""

from __future__ import annotations

import re

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.keyboards.menu import main_menu
from db.engine import AsyncSessionLocal
from db.repo import Repo
from services.crypto import CryptoService

router = Router()

WB_KEY_MIN_LEN = 200
WB_KEY_MAX_LEN = 2000
OZON_KEY_MIN_LEN = 20
OZON_KEY_MAX_LEN = 5000


class KeyStates(StatesGroup):
    waiting_wb_key = State()
    waiting_ozon_key = State()


def normalize_key(text: str) -> str:
    return text.strip()


def looks_like_key(text: str) -> bool:
    return len(text.strip()) >= 10


@router.message(F.text == "Подключить Wildberries")
async def connect_wb(message: Message, state: FSMContext) -> None:
    await state.set_state(KeyStates.waiting_wb_key)
    await message.answer(
        "Отправьте API ключ Wildberries одним сообщением.\n"
        "Ключ будет сохранён в БД в зашифрованном виде.\n\n"
        "Чтобы отменить — отправьте: Отмена",
        reply_markup=main_menu(),
    )


@router.message(F.text == "Подключить Ozon")
async def connect_ozon(message: Message, state: FSMContext) -> None:
    await state.set_state(KeyStates.waiting_ozon_key)
    await message.answer(
        "Отправьте Api-Key Ozon одним сообщением.\n"
        "Ключ будет сохранён в БД в зашифрованном виде.\n\n"
        "Чтобы отменить — отправьте: Отмена",
        reply_markup=main_menu(),
    )


@router.message(F.text == "Отмена")
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu())


@router.message(KeyStates.waiting_wb_key)
async def save_wb_key(message: Message, state: FSMContext) -> None:
    key = normalize_key(message.text or "")
    if not looks_like_key(key) or not (WB_KEY_MIN_LEN <= len(key) <= WB_KEY_MAX_LEN):
        await message.answer(
            f"Ключ WB выглядит некорректно.\n"
            f"Ожидаем длину примерно {WB_KEY_MIN_LEN}–{WB_KEY_MAX_LEN} символов.\n"
            f"Попробуйте ещё раз или отправьте: Отмена",
            reply_markup=main_menu(),
        )
        return

    crypto = CryptoService()
    encrypted = crypto.encrypt(key)

    async with AsyncSessionLocal() as session:
        repo = Repo(session)
        user = await repo.get_or_create_user(
            tg_user_id=message.from_user.id,
            tg_username=message.from_user.username,
        )
        await repo.upsert_credential(user.id, "wb", encrypted)

    await state.clear()
    # удаляем исходное сообщение с ключом для безопасности
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer("Ключ Wildberries сохранён. Мониторинг включён.", reply_markup=main_menu())


@router.message(KeyStates.waiting_ozon_key)
async def save_ozon_key(message: Message, state: FSMContext) -> None:
    key = normalize_key(message.text or "")
    if not looks_like_key(key) or not (OZON_KEY_MIN_LEN <= len(key) <= OZON_KEY_MAX_LEN):
        await message.answer(
            f"Ключ Ozon выглядит некорректно.\n"
            f"Ожидаем длину {OZON_KEY_MIN_LEN}–{OZON_KEY_MAX_LEN} символов.\n"
            f"Попробуйте ещё раз или отправьте: Отмена",
            reply_markup=main_menu(),
        )
        return

    crypto = CryptoService()
    encrypted = crypto.encrypt(key)

    async with AsyncSessionLocal() as session:
        repo = Repo(session)
        user = await repo.get_or_create_user(
            tg_user_id=message.from_user.id,
            tg_username=message.from_user.username,
        )
        await repo.upsert_credential(user.id, "ozon", encrypted)

    await state.clear()
    # удаляем исходное сообщение с ключом для безопасности
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer("Ключ Ozon сохранён. Мониторинг включён.", reply_markup=main_menu())


@router.message(F.text == "Отключить WB")
async def disable_wb(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        repo = Repo(session)
        user = await repo.get_or_create_user(
            tg_user_id=message.from_user.id,
            tg_username=message.from_user.username,
        )
        await repo.deactivate_credential(user.id, "wb")
    await message.answer("Wildberries отключён для мониторинга.", reply_markup=main_menu())


@router.message(F.text == "Отключить Ozon")
async def disable_ozon(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        repo = Repo(session)
        user = await repo.get_or_create_user(
            tg_user_id=message.from_user.id,
            tg_username=message.from_user.username,
        )
        await repo.deactivate_credential(user.id, "ozon")
    await message.answer("Ozon отключён для мониторинга.", reply_markup=main_menu())
