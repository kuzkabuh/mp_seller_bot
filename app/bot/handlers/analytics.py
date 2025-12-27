"""
Версия файла: 1.0.0
Описание: Команды аналитики для mp_seller_bot
Дата изменения: 2025-12-27
"""

from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message

from bot.keyboards.menu import main_menu
from db.engine import AsyncSessionLocal
from db.repo import Repo
from services.analytics_service import AnalyticsService

router = Router()


@router.message(F.text == "Аналитика за 7 дней")
async def analytics_7d(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        repo = Repo(session)
        user = await repo.get_or_create_user(
            tg_user_id=message.from_user.id,
            tg_username=message.from_user.username,
        )
        service = AnalyticsService(session)
        stats = await service.orders_count_last_days(user.id, days=7)

    if not stats:
        await message.answer("Пока нет событий заказов за последние 7 дней.", reply_markup=main_menu())
        return

    lines = ["Аналитика за 7 дней (по событиям):"]
    for k, v in sorted(stats.items()):
        lines.append(f"- {k}: {v}")

    await message.answer("\n".join(lines), reply_markup=main_menu())


@router.message(F.text == "Подсказки по выручке")
async def revenue_tips(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        service = AnalyticsService(session)
        tips = await service.revenue_tips_stub()

    text = "Подсказки по увеличению выручки:\n" + "\n".join([f"- {t}" for t in tips])
    await message.answer(text, reply_markup=main_menu())
