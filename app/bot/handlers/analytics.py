"""
Версия файла: 2.1.0
Описание: Команды аналитики для mp_seller_bot (меню аналитики, выбор маркетплейса, выручка/продажи/остатки/комиссии, единые ответы).
Дата изменения: 2025-12-28

Модуль реализует обработчики запросов к аналитике:
- базовая "Аналитика 7 дней" по событиям заказов
- заготовки разделов аналитики (выручка/продажи/остатки/комиссии/остатки)
- интеграция с меню клавиатур (analytics_menu, marketplace_menu, analytics_period_menu)
- подготовка к сценарию: Аналитика → период → выбор МП → вывод

Важно:
- Реальные метрики выручки/продаж/комиссий зависят от данных, которые мы начнём
  сохранять из API WB/Ozon и/или событий в БД. Сейчас часть обработчиков отдаёт
  понятные заглушки и объясняет, что нужно подключить сбор данных.
- Не выводим секреты/токены, только агрегаты.

Следующий файл, который желательно прислать:
- services/analytics_service.py (чтобы добавить реальные методы: revenue_last_days, sales_last_days, commissions_last_days, stocks_snapshot)
и/или
- db/models.py (чтобы понять, какие таблицы/поля уже есть для расчётов).
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from bot.keyboards.menu import (
    BTN_ANALYTICS,
    BTN_ANALYTICS_7,
    BTN_BACK_TO_MENU,
    BTN_COMMISSION,
    BTN_REVENUE,
    BTN_SALES,
    BTN_STOCKS,
    analytics_menu,
    main_menu,
)
from db import SessionLocal
from db.repo import Repo
from services.analytics_service import AnalyticsService

router = Router()


@router.message(F.text == BTN_ANALYTICS)
async def analytics_root(message: Message) -> None:
    """
    Открывает раздел «Аналитика» (меню).
    """
    await message.answer("Раздел «Аналитика». Выберите тип:", reply_markup=analytics_menu())


@router.message(F.text == BTN_BACK_TO_MENU)
async def analytics_back_to_menu(message: Message) -> None:
    """
    На случай, если этот модуль подключен раньше help/fallback и перехватит кнопку.
    """
    await message.answer("Главное меню.", reply_markup=main_menu())


@router.message(F.text == BTN_ANALYTICS_7)
@router.message(F.text == BTN_ANALYTICS_7.strip())
@router.message(F.text == "Аналитика за 7 дней")
async def analytics_7d(message: Message) -> None:
    """
    Выводит количество событий заказов за последние 7 дней.

    Счёт ведётся по таблице ``order_events`` и группируется по
    маркетплейсу и схеме (fbs/fbo). Если событий нет, пользователю
    выводится соответствующее сообщение.
    """
    async with SessionLocal() as session:
        repo = Repo(session)
        user = await repo.get_or_create_user(
            tg_user_id=message.from_user.id,
            tg_username=message.from_user.username,
        )
        service = AnalyticsService(session)
        stats = await service.orders_count_last_days(user.id, days=7)

    if not stats:
        await message.answer("Пока нет событий заказов за последние 7 дней.", reply_markup=analytics_menu())
        return

    lines = ["Аналитика за 7 дней (по событиям):"]
    for k, v in sorted(stats.items()):
        lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append("Для детальной аналитики подключите сбор данных из WB/Ozon и используйте разделы: Выручка, Продажи, Комиссии, Остатки.")

    await message.answer("\n".join(lines), reply_markup=analytics_menu())


@router.message(F.text == BTN_REVENUE)
async def revenue(message: Message) -> None:
    """
    Выручка — пока как заглушка/объяснение, т.к. реальные расчёты требуют
    сохранённых финансовых данных (платежи/реализации/комиссии) из API.
    """
    async with SessionLocal() as session:
        repo = Repo(session)
        user = await repo.get_or_create_user(
            tg_user_id=message.from_user.id,
            tg_username=message.from_user.username,
        )
        service = AnalyticsService(session)

        # Если сервис уже умеет — используем. Иначе отдаём объяснение.
        result = None
        if hasattr(service, "revenue_last_days"):
            try:
                result = await service.revenue_last_days(user.id, days=7)
            except Exception:
                result = None

    if not result:
        text = (
            "Выручка: пока нет данных для расчёта.\n\n"
            "Чтобы появился этот отчёт, нужно:\n"
            "1) Подключить ключи WB/Ozon в разделе «Подключения»\n"
            "2) В воркере начать регулярно забирать финансовые показатели через API и сохранять в БД\n\n"
            "После этого здесь будет выручка за период по WB/Ozon и динамика."
        )
        await message.answer(text, reply_markup=analytics_menu())
        return

    # Ожидаем, что result — словарь вида {"wb": 12345.67, "ozon": 8901.23} или похожее
    lines = ["Выручка за 7 дней:"]
    if isinstance(result, dict):
        for k, v in sorted(result.items()):
            lines.append(f"- {k}: {v}")
    else:
        lines.append(str(result))
    await message.answer("\n".join(lines), reply_markup=analytics_menu())


@router.message(F.text == BTN_SALES)
async def sales(message: Message) -> None:
    """
    Продажи — заготовка.
    """
    async with SessionLocal() as session:
        repo = Repo(session)
        user = await repo.get_or_create_user(
            tg_user_id=message.from_user.id,
            tg_username=message.from_user.username,
        )
        service = AnalyticsService(session)

        result = None
        if hasattr(service, "sales_last_days"):
            try:
                result = await service.sales_last_days(user.id, days=7)
            except Exception:
                result = None

    if not result:
        text = (
            "Продажи: пока нет данных для расчёта.\n\n"
            "Нужно начать сохранять фактические продажи/отгрузки из WB/Ozon (воркер + БД).\n"
            "После этого здесь будет количество продаж, сумма и разбивка по маркетплейсу."
        )
        await message.answer(text, reply_markup=analytics_menu())
        return

    lines = ["Продажи за 7 дней:"]
    if isinstance(result, dict):
        for k, v in sorted(result.items()):
            lines.append(f"- {k}: {v}")
    else:
        lines.append(str(result))
    await message.answer("\n".join(lines), reply_markup=analytics_menu())


@router.message(F.text == BTN_COMMISSION)
async def commissions(message: Message) -> None:
    """
    Комиссии — заготовка.
    """
    async with SessionLocal() as session:
        repo = Repo(session)
        user = await repo.get_or_create_user(
            tg_user_id=message.from_user.id,
            tg_username=message.from_user.username,
        )
        service = AnalyticsService(session)

        result = None
        if hasattr(service, "commissions_last_days"):
            try:
                result = await service.commissions_last_days(user.id, days=7)
            except Exception:
                result = None

    if not result:
        text = (
            "Комиссии: пока нет данных для расчёта.\n\n"
            "Нужно сохранять финансовые удержания/комиссии из API WB/Ozon.\n"
            "После этого здесь будет сумма комиссий за период и разбивка по маркетплейсу."
        )
        await message.answer(text, reply_markup=analytics_menu())
        return

    lines = ["Комиссии за 7 дней:"]
    if isinstance(result, dict):
        for k, v in sorted(result.items()):
            lines.append(f"- {k}: {v}")
    else:
        lines.append(str(result))
    await message.answer("\n".join(lines), reply_markup=analytics_menu())


@router.message(F.text == BTN_STOCKS)
async def stocks(message: Message) -> None:
    """
    Остатки — заготовка.
    """
    async with SessionLocal() as session:
        repo = Repo(session)
        user = await repo.get_or_create_user(
            tg_user_id=message.from_user.id,
            tg_username=message.from_user.username,
        )
        service = AnalyticsService(session)

        result = None
        if hasattr(service, "stocks_snapshot"):
            try:
                result = await service.stocks_snapshot(user.id)
            except Exception:
                result = None

    if not result:
        text = (
            "Остатки: пока нет данных для отчёта.\n\n"
            "Чтобы появился отчёт по остаткам, нужно:\n"
            "1) Подключить ключи WB/Ozon\n"
            "2) В воркере периодически забирать остатки со складов по API и сохранять в БД\n\n"
            "После этого здесь будет краткая сводка по складам и товарам."
        )
        await message.answer(text, reply_markup=analytics_menu())
        return

    # Если результат есть — покажем в человекочитаемом виде (ограниченно).
    lines = ["Остатки (снимок):"]
    if isinstance(result, dict):
        # не выводим слишком много строк
        shown = 0
        for k, v in sorted(result.items()):
            lines.append(f"- {k}: {v}")
            shown += 1
            if shown >= 20:
                lines.append("... (показаны первые 20 строк)")
                break
    else:
        lines.append(str(result))

    await message.answer("\n".join(lines), reply_markup=analytics_menu())


@router.message(F.text == "Подсказки по выручке")
async def revenue_tips(message: Message) -> None:
    """
    Совместимость со старой кнопкой/текстом.

    В текущей версии подсказки зашиты статически и служат демонстрацией.
    В будущем этот сервис может анализировать статистику пользователя и выдавать персональные советы.
    """
    async with SessionLocal() as session:
        service = AnalyticsService(session)
        tips = await service.revenue_tips_stub()

    text = "Подсказки по увеличению выручки:\n" + "\n".join([f"- {t}" for t in tips])
    await message.answer(text, reply_markup=analytics_menu())


"""
Какой файл прислать следующим:

1) services/analytics_service.py
   Я добавил использование возможных методов (revenue_last_days, sales_last_days, commissions_last_days, stocks_snapshot).
   Нужно либо реализовать их, либо явно оставить заглушки внутри сервиса единообразно.

2) Также полезно прислать workers/notifier.py (worker_loop),
   чтобы мы начали реально собирать минимум данных из API и складывать в БД,
   иначе аналитика так и останется "пока нет данных".

Начнём с services/analytics_service.py — пришли его следующим.
"""
