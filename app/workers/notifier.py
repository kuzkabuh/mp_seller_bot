# file: workers/notifier.py
# Версия файла: 2.1.0
# Описание: Асинхронный воркер для оповещений о новых заказах (параллельный опрос, лимиты, backoff, защита от флуда, health-метрики).
# Дата изменения: 2025-12-28

"""
Модуль notifier запускает фоновый цикл, который регулярно опрашивает маркетплейсы
Wildberries и Ozon на предмет новых заказов/отправлений. При обнаружении нового
события бот отправляет пользователю уведомление. Каждое событие дедуплицируется
с помощью таблицы order_events.

Ключевые улучшения:
- Параллельный опрос credential-ов с ограничением конкурентности (WORKER_CONCURRENCY).
- Rate-limit и защита от флуда: максимум уведомлений на один credential за один проход (MAX_NOTIFICATIONS_PER_CRED).
- Backoff при ошибках на уровне конкретного credential (в памяти процесса).
- Улучшенное форматирование сообщений и защита от слишком длинных сообщений.
- Единая обработка исключений и контекстные логи.
- Подготовка к расширению: метрики последнего успешного опроса (в памяти процесса).

Переменные окружения (необязательные):
- WORKER_CONCURRENCY: число параллельных опросов credential (по умолчанию 5)
- MAX_NOTIFICATIONS_PER_CRED: лимит уведомлений за один poll для одной учётки (по умолчанию 20)
- WORKER_BACKOFF_BASE_SECONDS: базовая задержка при ошибке (по умолчанию 30)
- WORKER_BACKOFF_MAX_SECONDS: максимальная задержка (по умолчанию 600)
- WORKER_ITEM_LIMIT_PER_SCHEME: ограничение количества элементов, которые обрабатываем за проход на схему (по умолчанию 200)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

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


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except Exception:
        return default


def _clamp_int(value: int, min_v: int, max_v: int) -> int:
    if value < min_v:
        return min_v
    if value > max_v:
        return max_v
    return value


def _now_ts() -> float:
    return time.time()


@dataclass
class BackoffState:
    """
    Backoff по credential (в памяти процесса).
    """
    next_allowed_ts: float = 0.0
    fails: int = 0


_BACKOFF: dict[int, BackoffState] = {}
_LAST_OK_POLL_TS: float = 0.0


async def poll_once(bot: Bot) -> None:
    """
    Выполняет один цикл опроса всех активных учётных записей.

    Получаем список активных credential-ов и обрабатываем их параллельно
    с ограничением конкурентности.
    """
    global _LAST_OK_POLL_TS

    concurrency = _clamp_int(_int_env("WORKER_CONCURRENCY", 5), 1, 50)

    async with SessionLocal() as session:
        repo = Repo(session)
        credentials: Sequence[MarketplaceCredential] = await repo.list_active_credentials()

    if not credentials:
        logger.debug("Нет активных marketplace_credentials для опроса")
        _LAST_OK_POLL_TS = _now_ts()
        return

    sem = asyncio.Semaphore(concurrency)

    async def _guarded(cred: MarketplaceCredential) -> None:
        async with sem:
            await _poll_credential(bot, cred)

    tasks = [asyncio.create_task(_guarded(cred), name=f"poll_cred_{cred.id}") for cred in credentials]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Логируем только агрегированно, чтобы не шуметь
    errors = sum(1 for r in results if isinstance(r, Exception))
    if errors:
        logger.warning("poll_once completed with errors: %s/%s", errors, len(results))
    else:
        logger.debug("poll_once completed успешно: %s credential(s)", len(results))

    _LAST_OK_POLL_TS = _now_ts()


async def _poll_credential(bot: Bot, cred: MarketplaceCredential) -> None:
    """
    Опрос одной учётной записи (credential) с учётом backoff.
    Внутри открываем отдельную DB-сессию, чтобы параллельность не ломала транзакции.
    """
    # Backoff check
    state = _BACKOFF.get(cred.id) or BackoffState()
    if state.next_allowed_ts > _now_ts():
        logger.debug(
            "Skip cred.id=%s marketplace=%s (backoff). next_allowed_in=%ss",
            cred.id,
            cred.marketplace,
            int(state.next_allowed_ts - _now_ts()),
        )
        _BACKOFF[cred.id] = state
        return

    crypto = CryptoService()

    # Расшифровываем ключи (вне db session не критично)
    try:
        api_key = crypto.decrypt(cred.encrypted_api_key)
        client_id: Optional[str] = None
        if getattr(cred, "encrypted_client_id", None):
            client_id = crypto.decrypt(cred.encrypted_client_id)
    except Exception as exc:
        logger.error(
            "Не удалось расшифровать ключи для cred.id=%s user_id=%s tg_user_id=%s marketplace=%s: %s",
            cred.id,
            cred.user_id,
            getattr(cred, "tg_user_id", None),
            cred.marketplace,
            exc,
        )
        _apply_backoff(cred.id)
        return

    try:
        async with SessionLocal() as session:
            repo = Repo(session)

            if cred.marketplace == "wb":
                await _poll_wb(session, repo, bot, cred, api_key)
            elif cred.marketplace == "ozon":
                await _poll_ozon(session, repo, bot, cred, api_key, client_id)
            else:
                logger.warning("Неизвестный marketplace='%s' для cred.id=%s", cred.marketplace, cred.id)
                return

        # Успешный проход по credential
        _clear_backoff(cred.id)
    except Exception as exc:
        logger.exception("Ошибка опроса cred.id=%s marketplace=%s: %s", cred.id, cred.marketplace, exc)
        _apply_backoff(cred.id)


def _apply_backoff(cred_id: int) -> None:
    base = _clamp_int(_int_env("WORKER_BACKOFF_BASE_SECONDS", 30), 5, 3600)
    max_s = _clamp_int(_int_env("WORKER_BACKOFF_MAX_SECONDS", 600), 10, 24 * 3600)

    st = _BACKOFF.get(cred_id) or BackoffState()
    st.fails += 1

    # Простейший экспоненциальный backoff без random-jitter, чтобы не усложнять.
    delay = base * (2 ** max(st.fails - 1, 0))
    if delay > max_s:
        delay = max_s

    st.next_allowed_ts = _now_ts() + float(delay)
    _BACKOFF[cred_id] = st

    logger.warning("Backoff applied for cred.id=%s fails=%s delay=%ss", cred_id, st.fails, int(delay))


def _clear_backoff(cred_id: int) -> None:
    if cred_id in _BACKOFF:
        _BACKOFF.pop(cred_id, None)


def _slice_items(items: Iterable[dict], limit: int) -> list[dict]:
    out: list[dict] = []
    for x in items:
        out.append(x)
        if len(out) >= limit:
            break
    return out


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
    item_limit = _clamp_int(_int_env("WORKER_ITEM_LIMIT_PER_SCHEME", 200), 1, 5000)

    # FBS
    try:
        fbs_items = await client.get_new_orders_fbs()
        await _process_items(
            session=session,
            repo=repo,
            bot=bot,
            cred=cred,
            scheme="fbs",
            items=_slice_items(fbs_items, item_limit),
            fallback_fields=("id", "orderId", "rid", "srid"),
        )
    except Exception as exc:
        logger.exception("Ошибка запроса WB FBS для cred.id=%s: %s", cred.id, exc)
        raise

    # FBO
    try:
        fbo_items = await client.get_new_orders_fbo()
        await _process_items(
            session=session,
            repo=repo,
            bot=bot,
            cred=cred,
            scheme="fbo",
            items=_slice_items(fbo_items, item_limit),
            fallback_fields=("id", "orderId", "rid", "srid"),
        )
    except Exception as exc:
        logger.exception("Ошибка запроса WB FBO для cred.id=%s: %s", cred.id, exc)
        raise


async def _poll_ozon(
    session: AsyncSession,
    repo: Repo,
    bot: Bot,
    cred: MarketplaceCredential,
    api_key: str,
    client_id: Optional[str],
) -> None:
    """
    Опрос заказов Ozon (FBS и FBO) для одной учётной записи.
    Требует наличия client_id.
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
    item_limit = _clamp_int(_int_env("WORKER_ITEM_LIMIT_PER_SCHEME", 200), 1, 5000)

    # FBS
    try:
        fbs_items = await client.get_new_postings_fbs()
        await _process_items(
            session=session,
            repo=repo,
            bot=bot,
            cred=cred,
            scheme="fbs",
            items=_slice_items(fbs_items, item_limit),
            fallback_fields=("posting_number", "posting_id", "id"),
        )
    except Exception as exc:
        logger.exception("Ошибка запроса Ozon FBS для cred.id=%s: %s", cred.id, exc)
        raise

    # FBO
    try:
        fbo_items = await client.get_new_postings_fbo()
        await _process_items(
            session=session,
            repo=repo,
            bot=bot,
            cred=cred,
            scheme="fbo",
            items=_slice_items(fbo_items, item_limit),
            fallback_fields=("posting_number", "posting_id", "id"),
        )
    except Exception as exc:
        logger.exception("Ошибка запроса Ozon FBO для cred.id=%s: %s", cred.id, exc)
        raise


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

    Защита от флуда:
    - ограничиваем кол-во уведомлений на credential за один проход.
    """
    _ = session  # session может понадобиться далее (например, для bulk-операций)

    max_notify = _clamp_int(_int_env("MAX_NOTIFICATIONS_PER_CRED", 20), 1, 200)
    notified = 0

    for item in items:
        if notified >= max_notify:
            logger.warning(
                "Достигнут лимит уведомлений за проход. cred.id=%s marketplace=%s scheme=%s limit=%s",
                cred.id,
                cred.marketplace,
                scheme,
                max_notify,
            )
            break

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

        # Короткое сообщение, чтобы не превышать лимиты и не светить лишнее
        marketplace_label = str(getattr(cred, "marketplace", "")).upper()
        scheme_label = str(scheme).upper()

        text = f"{marketplace_label} {scheme_label}: новое поступление\nID: {ext_id}"

        # Telegram ограничивает длину сообщения (практически 4096), оставляем запас
        if len(text) > 3500:
            text = text[:3500] + "…"

        try:
            await bot.send_message(chat_id=chat_id, text=text)
            notified += 1
        except Exception as exc:
            logger.error("Не удалось отправить сообщение tg_user_id=%s: %s", chat_id, exc)


async def worker_loop(bot: Bot) -> None:
    """
    Запускает бесконечный цикл опроса маркетплейсов.

    Вызывает poll_once раз в settings.poll_interval_seconds секунд.
    Логирует любые исключения и продолжает выполнение.
    """
    interval = getattr(settings, "poll_interval_seconds", 60)
    try:
        interval = int(interval)
    except Exception:
        interval = 60
    if interval < 5:
        interval = 5

    logger.info("Notifier worker started. interval=%s sec", interval)

    while True:
        try:
            await poll_once(bot)
        except Exception:
            logger.exception("Poll loop error")
        await asyncio.sleep(interval)


def get_worker_health() -> dict:
    """
    Небольшая служебная функция для будущего /health расширения.
    Сейчас нигде не используется, но пригодится для API/эндпоинта статуса.

    Возвращает:
    - last_ok_poll_ts: timestamp последнего завершённого poll_once
    - backoff_count: сколько credential сейчас в backoff
    """
    return {
        "last_ok_poll_ts": _LAST_OK_POLL_TS,
        "backoff_count": len(_BACKOFF),
    }
