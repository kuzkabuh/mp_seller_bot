# Файл: services/wb_client.py
# Версия файла: 2.1.0
# Описание: Асинхронный клиент Wildberries API для получения новых заказов (FBS + заготовка FBO),
#           с таймаутами, ретраями, валидацией ответов и безопасным логированием.
# Дата изменения: 2025-12-28

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class WBClient:
    """
    Асинхронный клиент для работы с API Wildberries.

    Особенности реализации:
    - Асинхронный httpx.AsyncClient
    - Таймауты и ограниченные ретраи
    - Аккуратная обработка неожиданных ответов API
    - Отсутствие логирования токена
    - Единый интерфейс под воркер notifier

    Используемые эндпоинты:
    - FBS: GET https://marketplace-api.wildberries.ru/api/v3/orders/new
    - FBO: пока отсутствует (заглушка)
    """

    BASE_URL = "https://marketplace-api.wildberries.ru"
    FBS_NEW_ORDERS_PATH = "/api/v3/orders/new"

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 30.0,
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ) -> None:
        """
        :param api_key: API-ключ Wildberries (передаётся в заголовке Authorization)
        :param timeout: таймаут HTTP-запросов в секундах
        :param max_retries: количество повторных попыток при сетевых ошибках
        :param retry_delay: базовая задержка между ретраями (сек)
        """
        self.api_key = api_key
        self.timeout = float(timeout)
        self.max_retries = max(0, int(max_retries))
        self.retry_delay = max(0.0, float(retry_delay))

    def _headers(self) -> Dict[str, str]:
        """
        Заголовки для запросов к WB API.
        """
        return {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Выполняет HTTP-запрос с ретраями и возвращает JSON-ответ.

        :raises httpx.HTTPError: при ошибках запроса или статусах 4xx/5xx
        :raises ValueError: если ответ не является JSON-объектом
        """
        last_exc: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=self._headers(),
                        params=params,
                    )
                response.raise_for_status()

                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("WB API response is not a JSON object")
                return data

            except (httpx.HTTPError, ValueError) as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    break
                delay = self.retry_delay * (2 ** attempt)
                logger.warning(
                    "WB API request failed (attempt %s/%s). Retrying in %.1fs. Error: %s",
                    attempt + 1,
                    self.max_retries + 1,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)

        assert last_exc is not None
        raise last_exc

    async def get_new_orders_fbs(self) -> List[Dict[str, Any]]:
        """
        Возвращает список новых FBS-заказов Wildberries.

        Ожидаемый формат ответа (упрощённо):
        {
            "orders": [ {...}, {...} ]
        }

        :return: список словарей заказов
        """
        url = f"{self.BASE_URL}{self.FBS_NEW_ORDERS_PATH}"
        data = await self._request_json("GET", url)

        orders = data.get("orders")
        if isinstance(orders, list):
            # Гарантируем, что каждый элемент — dict
            clean: List[Dict[str, Any]] = []
            for item in orders:
                if isinstance(item, dict):
                    clean.append(item)
                else:
                    logger.debug("WB FBS order item is not dict, skipped: %r", item)
            return clean

        logger.debug("WB FBS response has no 'orders' list or it is empty")
        return []

    async def get_new_orders_fbo(self) -> List[Dict[str, Any]]:
        """
        Заглушка для FBO-заказов Wildberries.

        На текущий момент (конец 2025) официальный эндпоинт
        для новых FBO-заказов в WB API отсутствует либо нестабилен.

        Когда появится официальный метод:
        - здесь будет добавлен реальный HTTP-запрос
        - интерфейс метода менять не потребуется

        :return: пустой список
        """
        return []
