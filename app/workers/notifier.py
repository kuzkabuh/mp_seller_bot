# Версия файла: 2.0.0
# Описание: Асинхронный воркер для оповещений о новых заказах.
# Обновлён для работы с новой моделью MarketplaceCredential
# и использования сервисов шифрования и клиентов.
# Дата изменения: 2025-12-27

"""
Модуль ``notifier`` запускает фоновый цикл, который регулярно
опрашивает маркетплейсы Wildberries и Ozon на предмет новых
заказов/отправлений. При обнаружении нового события бот
отправляет пользователю уведомление. Каждое событие
дедуплицируется с помощью таблицы ``order_events``.

Работает следующим образом:

* Получает список всех активных учётных записей (credentials).
* Расшифровывает API‑ключ и client_id с помощью CryptoService.
* В зависимости от маркетплейса инициирует клиент (WBClient или OzonClient).
* Получает новые заказы (FBS/FBO) и для каждого проверяет наличие в базе.
* Если событие новое, записывает его и отправляет сообщение пользователю.

Функция ``worker_loop`` запускает ``poll_once`` в бесконечном цикле с
интервалом, заданным в конфигурации. Все исключения логируются, но
не останавливают работу воркера.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Iterable

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import SessionLocal
from db.repo import Repo
from services.crypto import CryptoService
from services.order_detector import safe_external_id, to_json
from services.ozon_client import OzonClient
from services.wb_client import WBClient

logger = logging.getLogger("workers.notifier")


async def poll_once(bot: Bot) -> None:
    """
    Выполняет один цикл опроса всех активных учётных записей.

    Для каждого credentials расшифровывает ключи, запрашивает
    новые заказы и отправляет уведомления. Использует репозиторий
    для записи событий.
    """
    crypto = CryptoService()
    async with SessionLocal() as session:
        repo = Repo(session)
        credentials = await repo.list_active_credentials()
        for cred in credentials:
            # Расшифровываем ключи
            try:
                api_key = crypto.decrypt(cred.encrypted_api_key)
                client_id = None
                if cred.encrypted_client_id:
                    client_id = crypto.decrypt(cred.encrypted_client_id)
            except Exception as exc:
                logger.error("Не удалось расшифровать ключи для user_id=%s marketplace=%s: %s", cred.user_id, cred.marketplace, exc)
                continue

            if cred.marketplace == "wb":
                client = WBClient(api_key=api_key)
                # Запрашиваем FBS и FBO заказы
                try:
                    fbs_items = await client.get_new_orders_fbs()
                    await _process_items(session, repo, bot, cred, "fbs", fbs_items, fallback_fields=("id", "orderId", "rid", "srid"))
                except Exception as exc:
                    logger.exception("Ошибка запроса WB FBS: %s", exc)
                try:
                    fbo_items = await client.get_new_orders_fbo()
                    await _process_items(session, repo, bot, cred, "fbo", fbo_items, fallback_fields=("id", "orderId", "rid", "srid"))
                except Exception as exc:
                    logger.exception("Ошибка запроса WB FBO: %s", exc)

            elif cred.marketplace == "ozon" and client_id:
                client = OzonClient(api_key=api_key, client_id=client_id)
                try:
                    fbs_items = await client.get_new_postings_fbs()
                    await _process_items(session, repo, bot, cred, "fbs", fbs_items, fallback_fields=("posting_number", "posting_id", "id"))
                except Exception as exc:
                    logger.exception("Ошибка запроса Ozon FBS: %s", exc)
                try:
                    fbo_items = await client.get_new_postings_fbo()
                    await _process_items(session, repo, bot, cred, "fbo", fbo_items, fallback_fields=("posting_number", "posting_id", "id"))
                except Exception as exc:
                    logger.exception("Ошибка запроса Ozon FBO: %s", exc)


async def _process_items(
    session: AsyncSession,
    repo: Repo,
    bot: Bot,
    cred,
    scheme: str,
    items: Iterable[dict],
    fallback_fields: Iterable[str],
) -> None:
    """
    Обрабатывает список заказов/отправлений.

    Для каждого элемента вычисляет внешний идентификатор, записывает
    событие в БД (если оно новое) и отправляет уведомление.

    :param session: текущая сессия БД
    :param repo: репозиторий для доступа к данным
    :param bot: экземпляр бота для отправки сообщений
    :param cred: объект MarketplaceCredential
    :param scheme: схема (``"fbs"`` или ``"fbo"``)
    :param items: Iterable элементов (словарей) от API
    :param fallback_fields: поля, по которым можно получить идентификатор
    """
    for item in items:
        ext_id = safe_external_id(item, fallback_fields)
        is_new = await repo.insert_order_event_if_new(
            user_id=cred.user_id,
            marketplace=cred.marketplace,
            scheme=scheme,
            external_id=ext_id,
            payload_json=to_json(item),
        )
        if is_new:
            try:
                await bot.send_message(
                    chat_id=cred.tg_user_id,
                    text=f"{cred.marketplace.upper()} {scheme.upper()}: новое поступление\nID: {ext_id}",
                )
            except Exception as exc:
                logger.error("Не удалось отправить сообщение user_id=%s: %s", cred.tg_user_id, exc)


async def worker_loop(bot: Bot) -> None:
    """
    Запускает бесконечный цикл опроса маркетплейсов.

    Вызывает ``poll_once`` раз в ``settings.poll_interval_seconds`` секунд.
    Логирует любые исключения и продолжает выполнение.
    """
    logger.info("Notifier worker started. interval=%s sec", settings.poll_interval_seconds)
    while True:
        try:
            await poll_once(bot)
        except Exception:
            logger.exception("Poll loop error")
        await asyncio.sleep(settings.poll_interval_seconds)