# Версия файла: 2.0.1
# Описание: Асинхронный воркер для оповещений о новых заказах.
# Обновлён для работы с моделью MarketplaceCredential
# и использования сервисов шифрования и клиентов.
# Дата изменения: 2025-12-28

"""
Модуль ``notifier`` запускает фоновый цикл, который регулярно
опрашивает маркетплейсы Wildberries и Ozon на предмет новых
заказов/отправлений. При обнаружении нового события бот
отправляет пользователю уведомление. Каждое событие
дедуплицируется с помощью таблицы ``order_events``.

Работает следующим образом:

* Получает список всех активных учётных записей (credentials).
* Расшифровывает API-ключ и client_id с помощью CryptoService.
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
from typing import Iterable, Sequence

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import SessionLocal
from db.models import MarketplaceCredential
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

        # Получаем все активные креды (WB и Ozon) с tg_user_id.
        credentials: Sequence[MarketplaceCredential] = await repo.list_active_credentials()
        if not credentials:
            logger.debug("Нет активных marketplace_credentials для опроса")
            return

        for cred in credentials:
            # Расшифровываем ключи для конкретного маркетплейса
            try:
                api_key = crypto.decrypt(cred.encrypted_api_key)
                client_id = None
                if getattr(cred, "encrypted_client_id", None):
                    client_id = crypto.decrypt(cred.encrypted_client_id)
            except Exception as exc:
                logger.error(
                    "Не удалось расшифровать ключи для user_id=%s tg_user_id=%s marketplace=%s: %s",
                    cred.user_id,
                    getattr(cred, "tg_user_id", None),
                    cred.marketplace,
                    exc,
                )
                continue

            if cred.marketplace == "wb":
                await _poll_wb(session, repo, bot, cred, api_key)
            elif cred.marketplace == "ozon":
                await _poll_ozon(session, repo, bot, cred, api_key, client_id)
            else:
                logger.warning("Неизвестный marketplace='%s' для cred.id=%s", cred.marketplace, cred.id)


async def _poll_wb(
    session: AsyncSession,
    repo: Repo,
    bot: Bot,
    cred: MarketplaceCredential,
    api_key: str,
) -> None:
    """
    Опрос заказов Wildberries (FBS и FBO) для одной учётной записи.
    """
    client = WBClient(api_key=api_key)

    # FBS
    try:
        fbs_items = await client.get_new_orders_fbs()
        await _process_items(
            session=session,
            repo=repo,
            bot=bot,
            cred=cred,
            scheme="fbs",
            items=fbs_items,
            fallback_fields=("id", "orderId", "rid", "srid"),
        )
    except Exception as exc:
        logger.exception("Ошибка запроса WB FBS для cred.id=%s: %s", cred.id, exc)

    # FBO
    try:
        fbo_items = await client.get_new_orders_fbo()
        await _process_items(
            session=session,
            repo=repo,
            bot=bot,
            cred=cred,
            scheme="fbo",
            items=fbo_items,
            fallback_fields=("id", "orderId", "rid", "srid"),
        )
    except Exception as exc:
        logger.exception("Ошибка запроса WB FBO для cred.id=%s: %s", cred.id, exc)


async def _poll_ozon(
    session: AsyncSession,
    repo: Repo,
    bot: Bot,
    cred: MarketplaceCredential,
    api_key: str,
    client_id: str | None,
) -> None:
    """
    Опрос заказов Ozon (FBS и FBO) для одной учётной записи.

    Требует наличия client_id (иначе OzonClient не сможет авторизоваться).
    """
    if not client_id:
        logger.warning(
            "Ozon credentials без client_id для cred.id=%s user_id=%s tg_user_id=%s — пропускаем",
            cred.id,
            cred.user_id,
            getattr(cred, "tg_user_id", None),
        )
        return

    client = OzonClient(api_key=api_key, client_id=client_id)

    # FBS
    try:
        fbs_items = await client.get_new_postings_fbs()
        await _process_items(
            session=session,
            repo=repo,
            bot=bot,
            cred=cred,
            scheme="fbs",
            items=fbs_items,
            fallback_fields=("posting_number", "posting_id", "id"),
        )
    except Exception as exc:
        logger.exception("Ошибка запроса Ozon FBS для cred.id=%s: %s", cred.id, exc)

    # FBO
    try:
        fbo_items = await client.get_new_postings_fbo()
        await _process_items(
            session=session,
            repo=repo,
            bot=bot,
            cred=cred,
            scheme="fbo",
            items=fbo_items,
            fallback_fields=("posting_number", "posting_id", "id"),
        )
    except Exception as exc:
        logger.exception("Ошибка запроса Ozon FBO для cred.id=%s: %s", cred.id, exc)


async def _process_items(
    session: AsyncSession,
    repo: Repo,
    bot: Bot,
    cred: MarketplaceCredential,
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

        if not is_new:
            continue

        # Отправляем уведомление пользователю
        chat_id = getattr(cred, "tg_user_id", None)
        if not chat_id:
            logger.warning(
                "Новое событие marketplace=%s scheme=%s ext_id=%s, но tg_user_id не задан для cred.id=%s",
                cred.marketplace,
                scheme,
                ext_id,
                cred.id,
            )
            continue

        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"{cred.marketplace.upper()} {scheme.upper()}: новое поступление\nID: {ext_id}",
            )
        except Exception as exc:
            logger.error("Не удалось отправить сообщение tg_user_id=%s: %s", chat_id, exc)


async def worker_loop(bot: Bot) -> None:
    """
    Запускает бесконечный цикл опроса маркетплейсов.

    Вызывает ``poll_once`` раз в ``settings.poll_interval_seconds`` секунд.
    Логирует любые исключения и продолжает выполнение.
    """
    interval = getattr(settings, "poll_interval_seconds", 60)
    logger.info("Notifier worker started. interval=%s sec", interval)

    while True:
        try:
            await poll_once(bot)
        except Exception:
            logger.exception("Poll loop error")
        await asyncio.sleep(interval)
