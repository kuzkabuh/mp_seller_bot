"""
Версия файла: 2.0.0
Описание: Обработчики подключения и отключения ключей для Wildberries и Ozon.

Модуль предоставляет пользователю команды для отправки API ключей. Ключи
шифруются и сохраняются в базе данных. При подключении Ozon ожидаются
два значения: client_id и api_key, разделённые пробелом или двоеточием.
Дата изменения: 2025-12-27
"""

from __future__ import annotations

import re

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.keyboards.menu import main_menu
from db import SessionLocal
from db.repo import Repo
from services.crypto import CryptoService


router = Router()

# Ограничения по длине ключей
WB_KEY_MIN_LEN = 200
WB_KEY_MAX_LEN = 2000
OZON_KEY_MIN_LEN = 20
OZON_KEY_MAX_LEN = 5000
CLIENT_ID_MIN_LEN = 5
CLIENT_ID_MAX_LEN = 64


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
        "Отправьте API‑ключ Wildberries одним сообщением.\n"
        "Ключ будет сохранён в базе данных в зашифрованном виде.\n\n"
        "Чтобы отменить — отправьте: Отмена",
        reply_markup=main_menu(),
    )


@router.message(F.text == "Подключить Ozon")
async def connect_ozon(message: Message, state: FSMContext) -> None:
    await state.set_state(KeyStates.waiting_ozon_key)
    await message.answer(
        "Отправьте Client ID и Api‑Key Ozon в одном сообщении, разделив их пробелом или двоеточием.\n"
        "Пример: <code>12345678:abcdef0123456789</code>.\n"
        "Данные будут сохранены в базе в зашифрованном виде.\n\n"
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
    # Проверяем длину ключа
    if not looks_like_key(key) or not (WB_KEY_MIN_LEN <= len(key) <= WB_KEY_MAX_LEN):
        await message.answer(
            f"Ключ WB выглядит некорректно.\n"
            f"Ожидаем длину примерно {WB_KEY_MIN_LEN}–{WB_KEY_MAX_LEN} символов.\n"
            f"Попробуйте ещё раз или отправьте: Отмена",
            reply_markup=main_menu(),
        )
        return

    crypto = CryptoService()
    encrypted_key = crypto.encrypt(key)

    async with SessionLocal() as session:
        repo = Repo(session)
        user = await repo.get_or_create_user(
            tg_user_id=message.from_user.id,
            tg_username=message.from_user.username,
        )
        # Wildberries не требует client_id
        await repo.upsert_credential(
            user_id=user.id,
            tg_user_id=message.from_user.id,
            marketplace="wb",
            encrypted_api_key=encrypted_key,
            encrypted_client_id=None,
        )

    await state.clear()
    # Удаляем исходное сообщение с ключом для безопасности
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer("Ключ Wildberries сохранён. Мониторинг включён.", reply_markup=main_menu())


@router.message(KeyStates.waiting_ozon_key)
async def save_ozon_key(message: Message, state: FSMContext) -> None:
    raw = normalize_key(message.text or "")
    # Разделяем по пробелу или двоеточию
    parts = re.split(r"[\s:]+", raw)
    if len(parts) < 2:
        await message.answer(
            "Нужно указать два значения: Client ID и Api‑Key, разделённые пробелом или двоеточием.\n"
            "Пример: <code>12345678:abcdef0123456789</code>. Попробуйте ещё раз или отправьте: Отмена",
            reply_markup=main_menu(),
        )
        return
    client_id, api_key = parts[0], parts[1]
    if not (CLIENT_ID_MIN_LEN <= len(client_id) <= CLIENT_ID_MAX_LEN):
        await message.answer(
            f"Client ID выглядит некорректно (длина {len(client_id)}). Ожидаем {CLIENT_ID_MIN_LEN}–{CLIENT_ID_MAX_LEN} символов.",
            reply_markup=main_menu(),
        )
        return
    if not (OZON_KEY_MIN_LEN <= len(api_key) <= OZON_KEY_MAX_LEN):
        await message.answer(
            f"Api‑Key выглядит некорректно (длина {len(api_key)}). Ожидаем {OZON_KEY_MIN_LEN}–{OZON_KEY_MAX_LEN} символов.",
            reply_markup=main_menu(),
        )
        return

    crypto = CryptoService()
    encrypted_key = crypto.encrypt(api_key)
    encrypted_client_id = crypto.encrypt(client_id)

    async with SessionLocal() as session:
        repo = Repo(session)
        user = await repo.get_or_create_user(
            tg_user_id=message.from_user.id,
            tg_username=message.from_user.username,
        )
        await repo.upsert_credential(
            user_id=user.id,
            tg_user_id=message.from_user.id,
            marketplace="ozon",
            encrypted_api_key=encrypted_key,
            encrypted_client_id=encrypted_client_id,
        )

    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer("Учётные данные Ozon сохранены. Мониторинг включён.", reply_markup=main_menu())


@router.message(F.text == "Отключить WB")
async def disable_wb(message: Message) -> None:
    async with SessionLocal() as session:
        repo = Repo(session)
        user = await repo.get_or_create_user(
            tg_user_id=message.from_user.id,
            tg_username=message.from_user.username,
        )
        await repo.deactivate_credential(user.id, "wb")
    await message.answer("Wildberries отключён для мониторинга.", reply_markup=main_menu())


@router.message(F.text == "Отключить Ozon")
async def disable_ozon(message: Message) -> None:
    async with SessionLocal() as session:
        repo = Repo(session)
        user = await repo.get_or_create_user(
            tg_user_id=message.from_user.id,
            tg_username=message.from_user.username,
        )
        await repo.deactivate_credential(user.id, "ozon")
    await message.answer("Ozon отключён для мониторинга.", reply_markup=main_menu())