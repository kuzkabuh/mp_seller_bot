# Версия файла: 1.1.0
# Описание: Хэндлеры Telegram-бота (меню, подключение API ключей, статусы)
# Дата изменения: 2025-12-27

from __future__ import annotations

import logging
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from config import settings
from db import SessionLocal
from bot.key_store import get_api_key, upsert_api_key

logger = logging.getLogger("handlers")

router = Router()


def _mask_key(key: str) -> str:
    if len(key) <= 10:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    text = (
        "Seller Bot (WB / Ozon)\n\n"
        "Команды:\n"
        "/connect_wb — подключить Wildberries (API ключ)\n"
        "/connect_ozon — подключить Ozon (API ключ)\n"
        "/status — статус подключений\n"
        "/help — справка\n\n"
        "Важно: ключи сохраняются в БД в зашифрованном виде."
    )
    await message.answer(text)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Справка:\n\n"
        "1) Подключите маркетплейсы:\n"
        "   /connect_wb\n"
        "   /connect_ozon\n\n"
        "2) Проверьте статус:\n"
        "   /status\n\n"
        "Далее мы добавим:\n"
        "- уведомления по FBS/FBO\n"
        "- аналитику и подсказки по выручке\n"
        "- расписание обновлений\n"
    )


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    tg_user_id = message.from_user.id if message.from_user else 0
    if tg_user_id == 0:
        await message.answer("Не удалось определить пользователя Telegram.")
        return

    async with SessionLocal() as session:
        wb_key = await get_api_key(session, tg_user_id, "wb", settings.fernet_key)
        ozon_key = await get_api_key(session, tg_user_id, "ozon", settings.fernet_key)

    wb_status = f"подключен ({_mask_key(wb_key)})" if wb_key else "не подключен"
    ozon_status = f"подключен ({_mask_key(ozon_key)})" if ozon_key else "не подключен"

    await message.answer(
        "Статус подключений:\n"
        f"- Wildberries: {wb_status}\n"
        f"- Ozon: {ozon_status}\n"
    )


@router.message(Command("connect_wb"))
async def cmd_connect_wb(message: Message) -> None:
    await message.answer("Пришлите API ключ Wildberries одним сообщением. Длина ключа может быть ~500 символов.")


@router.message(Command("connect_ozon"))
async def cmd_connect_ozon(message: Message) -> None:
    await message.answer("Пришлите API ключ Ozon одним сообщением.")


@router.message(F.text)
async def catch_text(message: Message) -> None:
    """
    На этом этапе упрощаем: если пользователь последней командой был connect_* — он отправляет ключ.
    Для этого в следующем stage добавим FSM.
    Сейчас — минимально: определяем по префиксу текста (не идеально, но работает для старта).
    """
    tg_user_id = message.from_user.id if message.from_user else 0
    if tg_user_id == 0:
        return

    text = (message.text or "").strip()
    if not text:
        return

    # Простая эвристика:
    # - WB ключ часто длинный (~500) и может выглядеть как JWT/строка с точками/символами
    # - Ozon ключ может быть короче, но не гарантируем.
    # Сейчас: если длина >= 200 — считаем WB, иначе просим уточнить командой.
    marketplace: Optional[str] = None
    if len(text) >= 200:
        marketplace = "wb"

    if marketplace is None:
        await message.answer(
            "Я не понял, это ключ какого маркетплейса.\n"
            "Используйте команду:\n"
            "/connect_wb или /connect_ozon\n"
            "и затем пришлите ключ одним сообщением."
        )
        return

    async with SessionLocal() as session:
        await upsert_api_key(session, tg_user_id, marketplace, text, settings.fernet_key)

    await message.answer(f"Ключ сохранён для {('Wildberries' if marketplace == 'wb' else 'Ozon')} (зашифрован).")
