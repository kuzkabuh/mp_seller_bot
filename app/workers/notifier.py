# Версия файла: 1.1.0
# Описание: Воркер для уведомлений (добавлена поддержка Ozon Client ID)
# Дата изменения: 2025-12-27

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from sqlalchemy import select

from config import settings
from db import SessionLocal
from db.models import MarketplaceAccount
from services.ozon_client import OzonClient
from services.wb_client import WBClient
from services.order_detector import safe_external_id, to_json

logger = logging.getLogger("workers.notifier")


async def poll_once(bot: Bot) -> None:
    async with SessionLocal() as session:
        # Получаем все активные аккаунты
        q = select(MarketplaceAccount).where(MarketplaceAccount.is_active == True)  # noqa: E712
        res = await session.execute(q)
        accounts = res.scalars().all()

        for acc in accounts:
            # Дешифруем ключи в последнюю очередь (если понадобится)
            from security.crypto import build_fernet, decrypt_text

            fernet = build_fernet(settings.fernet_key)
            api_key = decrypt_text(fernet, acc.api_key_encrypted)
            client_id = None
            if acc.client_id_encrypted:
                client_id = decrypt_text(fernet, acc.client_id_encrypted)

            if acc.marketplace == "wb":
                client = WBClient(api_key=api_key)

                fbs_items = await client.get_new_orders_fbs()
                for item in fbs_items:
                    ext_id = safe_external_id(item, fallback_fields=("id", "orderId", "rid", "srid"))
                    is_new = await insert_event_if_new(session, acc.tg_user_id, "wb", "fbs", ext_id, item)
                    if is_new:
                        await bot.send_message(
                            chat_id=acc.tg_user_id,
                            text=f"WB FBS: новый заказ\nID: {ext_id}",
                        )

                fbo_items = await client.get_new_orders_fbo()
                for item in fbo_items:
                    ext_id = safe_external_id(item, fallback_fields=("id", "orderId", "rid", "srid"))
                    is_new = await insert_event_if_new(session, acc.tg_user_id, "wb", "fbo", ext_id, item)
                    if is_new:
                        await bot.send_message(
                            chat_id=acc.tg_user_id,
                            text=f"WB FBO: новый заказ\nID: {ext_id}",
                        )

            elif acc.marketplace == "ozon" and client_id:
                client = OzonClient(api_key=api_key, client_id=client_id)

                fbs_items = await client.get_new_postings_fbs()
                for item in fbs_items:
                    ext_id = safe_external_id(item, fallback_fields=("posting_number", "posting_id", "id"))
                    is_new = await insert_event_if_new(session, acc.tg_user_id, "ozon", "fbs", ext_id, item)
                    if is_new:
                        await bot.send_message(
                            chat_id=acc.tg_user_id,
                            text=f"Ozon FBS: новое отправление\nID: {ext_id}",
                        )

                fbo_items = await client.get_new_postings_fbo()
                for item in fbo_items:
                    ext_id = safe_external_id(item, fallback_fields=("posting_number", "posting_id", "id"))
                    is_new = await insert_event_if_new(session, acc.tg_user_id, "ozon", "fbo", ext_id, item)
                    if is_new:
                        await bot.send_message(
                            chat_id=acc.tg_user_id,
                            text=f"Ozon FBO: новое отправление\nID: {ext_id}",
                        )


async def insert_event_if_new(
    session: SessionLocal,
    tg_user_id: int,
    marketplace: str,
    scheme: str,
    external_id: str,
    payload: dict,
) -> bool:
    from db.models import OrderEvent  # импорт внутри функции во избежание циклов
    from sqlalchemy import select

    # Проверяем уникальность
    q = select(OrderEvent).where(
        OrderEvent.user_id == tg_user_id,
        OrderEvent.marketplace == marketplace,
        OrderEvent.scheme == scheme,
        OrderEvent.external_id == external_id,
    )
    res = await session.execute(q)
    row = res.scalar_one_or_none()
    if row:
        return False

    # Вставляем новую запись
    ev = OrderEvent(
        user_id=tg_user_id,
        marketplace=marketplace,
        scheme=scheme,
        external_id=external_id,
        payload_json=to_json(payload),
    )
    session.add(ev)
    await session.commit()
    return True


async def worker_loop(bot: Bot) -> None:
    logger.info("Notifier worker started. interval=%s sec", settings.poll_interval_seconds)

    while True:
        try:
            await poll_once(bot)
        except Exception:
            logger.exception("Poll loop error")
        await asyncio.sleep(settings.poll_interval_seconds)
