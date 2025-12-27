"""
Файл: services/ozon_client.py
Версия файла: 2.0.0
Описание: Асинхронный клиент Ozon API для получения FBS/FBO posting'ов
Дата изменения: 2025-12-28

Клиент OzonClient реализует безопасные и устойчивые запросы к API Ozon
для получения новых отправлений (postings) по схемам FBS и FBO.

Улучшения по сравнению с предыдущей версией:
- Добавлены таймауты и контролируемые ретраи с экспоненциальной задержкой
- Унифицирована внутренняя функция HTTP-запроса (_request_json)
- Защита от невалидных ответов API (не dict / отсутствующие ключи)
- Исключено логирование api_key и client_id
- Добавлены ограничения на параметры (limit, offset)
- Приведение результата строго к List[dict]
- Подготовка к дальнейшему расширению (фильтры по дате, пагинация)

Этот клиент используется воркером workers.notifier и должен быть
полностью асинхронным и безопасным.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class OzonClient:
    BASE_URL = "https://api-seller.ozon.ru"

    FBS_LIST_PATH = "/v3/posting/fbs/list"
    FBO_LIST_PATH = "/v2/posting/fbo/list"

    def __init__(
        self,
        api_key: str,
        client_id: str,
        *,
        timeout: float = 30.0,
        max_retries: int = 2,
        retry_delay: float = 1.0,
        limit: int = 50,
    ) -> None:
        """
        :param api_key: Api-Key Ozon
        :param client_id: Client-Id Ozon
        :param timeout: таймаут HTTP-запросов в секундах
        :param max_retries: количество повторных попыток при ошибках
        :param retry_delay: базовая задержка между ретраями
        :param limit: количество posting'ов за запрос (1–100)
        """
        self.api_key = api_key
        self.client_id = client_id
        self.timeout = float(timeout)
        self.max_retries = max(0, int(max_retries))
        self.retry_delay = max(0.0, float(retry_delay))
        self.limit = max(1, min(int(limit), 100))

    def _headers(self) -> Dict[str, str]:
        """
        Заголовки для запросов к Ozon API.
        """
        return {
            "Api-Key": self.api_key,
            "Client-Id": self.client_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request_json(
        self,
        path: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Выполняет POST-запрос к Ozon API с ретраями и возвращает JSON-ответ.

        :raises httpx.HTTPError: при сетевых ошибках или статусах 4xx/5xx
        :raises ValueError: если ответ не является JSON-объектом
        """
        url = f"{self.BASE_URL}{path}"
        last_exc: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers=self._headers(),
                    )
                response.raise_for_status()

                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Ozon API response is not a JSON object")

                return data

            except (httpx.HTTPError, ValueError) as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    break

                delay = self.retry_delay * (2 ** attempt)
                logger.warning(
                    "Ozon API request failed (attempt %s/%s). Retrying in %.1fs. Error: %s",
                    attempt + 1,
                    self.max_retries + 1,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)

        assert last_exc is not None
        raise last_exc

    def _base_payload(self) -> Dict[str, Any]:
        """
        Базовый payload для запросов posting list.
        """
        return {
            "filter": {
                "status": "awaiting_packaging",
            },
            "with": {
                "analytics_data": False,
                "financial_data": False,
            },
            "dir": "ASC",
            "limit": self.limit,
            "offset": 0,
        }

    async def get_new_postings_fbs(self) -> List[Dict[str, Any]]:
        """
        Получает список новых FBS posting'ов со статусом awaiting_packaging.

        API: POST /v3/posting/fbs/list

        :return: список posting'ов (list[dict])
        """
        payload = self._base_payload()
        data = await self._request_json(self.FBS_LIST_PATH, payload)

        postings = data.get("result", {}).get("postings", [])
        if not isinstance(postings, list):
            logger.debug("Ozon FBS response has no valid 'postings' list")
            return []

        clean: List[Dict[str, Any]] = []
        for item in postings:
            if isinstance(item, dict):
                clean.append(item)
            else:
                logger.debug("Ozon FBS posting item is not dict, skipped: %r", item)

        return clean

    async def get_new_postings_fbo(self) -> List[Dict[str, Any]]:
        """
        Получает список новых FBO posting'ов со статусом awaiting_packaging.

        API: POST /v2/posting/fbo/list

        :return: список posting'ов (list[dict])
        """
        payload = self._base_payload()
        data = await self._request_json(self.FBO_LIST_PATH, payload)

        postings = data.get("result", {}).get("postings", [])
        if not isinstance(postings, list):
            logger.debug("Ozon FBO response has no valid 'postings' list")
            return []

        clean: List[Dict[str, Any]] = []
        for item in postings:
            if isinstance(item, dict):
                clean.append(item)
            else:
                logger.debug("Ozon FBO posting item is not dict, skipped: %r", item)

        return clean
