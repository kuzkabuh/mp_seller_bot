"""
Версия файла: 1.0.0
Описание: Фоновый воркер проверки заказов WB/Ozon и отправки уведомлений
Дата изменения: 2025-12-27
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from config import settings
from db.engine import AsyncSessionLocal
from db.repo import Repo
from services.crypto import CryptoService
from services.order_detector import safe_external_id, to_json
from services.wb_client import WBClient
from services.ozon_client import OzonClient

logger = logging.getLogger("workers.notifier")


async def poll_once(bot: Bot) -> None:
    crypto = CryptoService()

    async with AsyncSessionLocal() as session:
        repo = Repo(session)
        creds = await repo.list_active_credentials()

        for cred in creds:
            try:
                api_key = crypto.decrypt(cred.encrypted_api_key)
            except Exception as e:
                logger.exception("Decrypt error user_id=%s marketplace=%s", cred.user_id, cred.marketplace)
                continue

            if cred.marketplace == "wb":
                client = WBClient(api_key=api_key)

                fbs_items = await client.get_new_orders_fbs()
                for item in fbs_items:
                    ext_id = safe_external_id(item, fallback_fields=("id", "orderId", "rid", "srid"))
                    is_new = await repo.insert_order_event_if_new(
                        user_id=cred.user_id,
                        marketplace="wb",
                        scheme="fbs",
                        external_id=ext_id,
                        payload_json=to_json(item),
                    )
                    if is_new:
                        await bot.send_message(
                            chat_id=(await _tg_user_id_by_internal(session, cred.user_id)),
                            text=f"WB FBS: новый заказ/событие\nID: {ext_id}",
                        )

                fbo_items = await client.get_new_orders_fbo()
                for item in fbo_items:
                    ext_id = safe_external_id(item, fallback_fields=("id", "orderId", "rid", "srid"))
                    is_new = await repo.insert_order_event_if_new(
                        user_id=cred.user_id,
                        marketplace="wb",
                        scheme="fbo",
                        external_id=ext_id,
                        payload_json=to_json(item),
                    )
                    if is_new:
                        await bot.send_message(
                            chat_id=(await _tg_user_id_by_internal(session, cred.user_id)),
                            text=f"WB FBO: новый заказ/событие\nID: {ext_id}",
                        )

            elif cred.marketplace == "ozon":
                client = OzonClient(api_key=api_key, client_id=None)

                fbs_items = await client.get_new_postings_fbs()
                for item in fbs_items:
                    ext_id = safe_external_id(item, fallback_fields=("posting_number", "posting_id", "id"))
                    is_new = await repo.insert_order_event_if_new(
                        user_id=cred.user_id,
                        marketplace="ozon",
                        scheme="fbs",
                        external_id=ext_id,
                        payload_json=to_json(item),
                    )
                    if is_new:
                        await bot.send_message(
                            chat_id=(await _tg_user_id_by_internal(session, cred.user_id)),
                            text=f"Ozon FBS: новый posting/событие\nID: {ext_id}",
                        )

                fbo_items = await client.get_new_postings_fbo()
                for item in fbo_items:
                    ext_id = safe_external_id(item, fallback_fields=("posting_number", "posting_id", "id"))
                    is_new = await repo.insert_order_event_if_new(
                        user_id=cred.user_id,
                        marketplace="ozon",
                        scheme="fbo",
                        external_id=ext_id,
                        payload_json=to_json(item),
                    )
                    if is_new:
                        await bot.send_message(
                            chat_id=(await _tg_user_id_by_internal(session, cred.user_id)),
                            text=f"Ozon FBO: новый posting/событие\nID: {ext_id}",
                        )


async def _tg_user_id_by_internal(session, internal_user_id: int) -> int:
    from sqlalchemy import select
    from db.models import User

    q = await session.execute(select(User.tg_user_id).where(User.id == internal_user_id))
    tg_user_id = q.scalar_one()
    return int(tg_user_id)


async def worker_loop(bot: Bot) -> None:
    logger.info("Notifier worker started. interval=%s sec", settings.POLL_INTERVAL_SECONDS)

    while True:
        try:
            await poll_once(bot)
        except Exception:
            logger.exception("Poll loop error")
        await asyncio.sleep(settings.POLL_INTERVAL_SECONDS)
