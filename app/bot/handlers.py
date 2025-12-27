# Версия файла: 1.1.2
# Описание: Хэндлеры Telegram-бота (меню, подключение API ключей, статусы, удаление сообщений, кнопки)
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
from bot.keyboards.menu import main_menu
from db.models import MarketplaceAccount
from sqlalchemy import delete

logger = logging.getLogger("handlers")

router = Router()


def _mask_key(key: str) -> str:
    if len(key) <= 10:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """
    Отправляет приветственное сообщение и отображает главное меню.
    """
    text = (
        "<b>Seller\u00a0Bot</b> (WB\u00a0/\u00a0Ozon)\n\n"
        "Используйте меню ниже или команды:\n"
        "• <code>/connect_wb</code> — подключить Wildberries (API ключ)\n"
        "• <code>/connect_ozon</code> — подключить Ozon (API ключ)\n"
        "• <code>/status</code> — статус подключений\n"
        "• <code>/help</code> — справка\n\n"
        "<i>Важно: ваши API‑ключи сохраняются в базе данных в зашифрованном виде.</i>"
    )
    await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    text = (
        "<b>Справка</b>:\n\n"
        "1. Подключите маркетплейсы:\n"
        "   • <code>/connect_wb</code> — сохранить API‑ключ Wildberries\n"
        "   • <code>/connect_ozon</code> — сохранить API‑ключ Ozon\n\n"
        "2. Проверьте статус:\n"
        "   • <code>/status</code> — показать подключённые аккаунты\n\n"
        "Далее мы планируем добавить:\n"
        "• уведомления по FBS/FBO\n"
        "• аналитику и подсказки по выручке\n"
        "• расписание обновлений и многое другое."
    )
    await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    tg_user_id = message.from_user.id if message.from_user else 0
    if tg_user_id == 0:
        await message.answer("Не удалось определить пользователя Telegram.", reply_markup=main_menu())
        return

    async with SessionLocal() as session:
        wb_key = await get_api_key(session, tg_user_id, "wb", settings.fernet_key)
        ozon_key = await get_api_key(session, tg_user_id, "ozon", settings.fernet_key)

    wb_status = f"подключен ({_mask_key(wb_key)})" if wb_key else "не подключен"
    ozon_status = f"подключен ({_mask_key(ozon_key)})" if ozon_key else "не подключен"

    await message.answer(
        f"<b>Статус подключений</b>:\n"
        f"• Wildberries: {wb_status}\n"
        f"• Ozon: {ozon_status}",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )


@router.message(Command("connect_wb"))
async def cmd_connect_wb(message: Message) -> None:
    await message.answer(
        "Пожалуйста, отправьте API‑ключ <b>Wildberries</b> одним сообщением.\n"
        "Ключ будет сохранён в базе данных в зашифрованном виде.",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )


@router.message(Command("connect_ozon"))
async def cmd_connect_ozon(message: Message) -> None:
    await message.answer(
        "Пожалуйста, отправьте API‑ключ <b>Ozon</b> одним сообщением.\n"
        "Ключ будет сохранён в базе данных в зашифрованном виде.",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )


# --- Обработчики нажатий кнопок меню ---


@router.message(F.text == "Подключить Wildberries")
async def btn_connect_wb(message: Message) -> None:
    await cmd_connect_wb(message)


@router.message(F.text == "Подключить Ozon")
async def btn_connect_ozon(message: Message) -> None:
    await cmd_connect_ozon(message)


@router.message(F.text == "Помощь")
async def btn_help(message: Message) -> None:
    await cmd_help(message)


@router.message(F.text == "Отключить WB")
async def btn_disable_wb(message: Message) -> None:
    tg_user_id = message.from_user.id if message.from_user else 0
    if tg_user_id == 0:
        return
    async with SessionLocal() as session:
        await session.execute(
            delete(MarketplaceAccount).where(
                MarketplaceAccount.tg_user_id == tg_user_id,
                MarketplaceAccount.marketplace == "wb",
            )
        )
        await session.commit()
    await message.answer("Подключение <b>Wildberries</b> отключено.", reply_markup=main_menu(), parse_mode="HTML")


@router.message(F.text == "Отключить Ozon")
async def btn_disable_ozon(message: Message) -> None:
    tg_user_id = message.from_user.id if message.from_user else 0
    if tg_user_id == 0:
        return
    async with SessionLocal() as session:
        await session.execute(
            delete(MarketplaceAccount).where(
                MarketplaceAccount.tg_user_id == tg_user_id,
                MarketplaceAccount.marketplace == "ozon",
            )
        )
        await session.commit()
    await message.answer("Подключение <b>Ozon</b> отключено.", reply_markup=main_menu(), parse_mode="HTML")


@router.message(F.text == "Аналитика за 7 дней")
async def btn_analytics_stub(message: Message) -> None:
    await message.answer(
        "Функция аналитики пока находится в разработке.\n"
        "Скоро вы сможете видеть статистику продаж и заказы за последние 7 дней.",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )


@router.message(F.text == "Подсказки по выручке")
async def btn_revenue_tips_stub(message: Message) -> None:
    await message.answer(
        "Функция подсказок по выручке пока находится в разработке.\n"
        "Скоро вы будете получать полезные советы по увеличению продаж.",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )


@router.message(F.text)
async def catch_text(message: Message) -> None:
    """
    Обрабатывает текстовые сообщения, предполагая, что это токен API.
    На текущем этапе используется простая эвристика для определения маркетплейса.
    """
    tg_user_id = message.from_user.id if message.from_user else 0
    if tg_user_id == 0:
        return

    text = (message.text or "").strip()
    if not text:
        return

    # Простая эвристика: если длина >= 200 — считаем WB, иначе просим уточнить
    marketplace: Optional[str] = None
    if len(text) >= 200:
        marketplace = "wb"

    if marketplace is None:
        await message.answer(
            "Я не понял, это ключ какого маркетплейса.\n"
            "Выберите пункт меню «Подключить Wildberries» или «Подключить Ozon» "
            "и затем пришлите ключ одним сообщением.",
            reply_markup=main_menu(),
        )
        return

    async with SessionLocal() as session:
        await upsert_api_key(session, tg_user_id, marketplace, text, settings.fernet_key)

    # удаляем исходное сообщение с ключом для безопасности
    try:
        await message.delete()
    except Exception:
        pass

    await message.answer(
        f"Ключ сохранён для {'<b>Wildberries</b>' if marketplace == 'wb' else '<b>Ozon</b>'} (зашифрован).",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )
