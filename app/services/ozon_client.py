"""
Версия файла: 1.2.0
Описание: Реализация методов Ozon API (FBS/FBO postings) с ретраями и улучшенным логированием.
Дата изменения: 2025-12-28

Изменения:
- добавлен единый метод _request_json() с повторными попытками и backoff
- улучшено логирование ошибок: выводится HTTP статус, тело ответа, request-id/correlation-id (если есть)
- добавлены безопасные таймауты и ограничения клиента httpx
- добавлены параметры limit/offset и базовая валидация входных данных
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger("services.ozon_client")


class OzonClient:
    """
    Асинхронный клиент для Ozon Seller API.

    Используется для получения отправлений (postings):
    - FBS: POST /v3/posting/fbs/list
    - FBO: POST /v2/posting/fbo/list

    Заголовки авторизации:
    - Api-Key
    - Client-Id
    """

    BASE_URL = "https://api-seller.ozon.ru"
    FBS_LIST_PATH = "/v3/posting/fbs/list"
    FBO_LIST_PATH = "/v2/posting/fbo/list"

    def __init__(
        self,
        api_key: str,
        client_id: str,
        timeout_seconds: float = 30.0,
        max_attempts: int = 3,
        backoff_base_seconds: float = 1.0,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.client_id = (client_id or "").strip()

        if not self.api_key:
            raise ValueError("OzonClient: api_key пустой")
        if not self.client_id:
            raise ValueError("OzonClient: client_id пустой")

        if timeout_seconds <= 0:
            raise ValueError("OzonClient: timeout_seconds должен быть > 0")
        if max_attempts < 1:
            raise ValueError("OzonClient: max_attempts должен быть >= 1")
        if backoff_base_seconds <= 0:
            raise ValueError("OzonClient: backoff_base_seconds должен быть > 0")

        self.timeout_seconds = float(timeout_seconds)
        self.max_attempts = int(max_attempts)
        self.backoff_base_seconds = float(backoff_base_seconds)

    def _headers(self) -> dict[str, str]:
        return {
            "Api-Key": self.api_key,
            "Client-Id": self.client_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "mp_seller_bot/ozon_client/1.2.0",
        }

    @staticmethod
    def _extract_request_ids(response: httpx.Response) -> dict[str, str]:
        """
        В Ozon иногда полезные идентификаторы лежат в заголовках.
        Мы вытаскиваем наиболее часто встречающиеся.
        """
        keys = [
            "x-request-id",
            "x-correlation-id",
            "x-trace-id",
            "x-amzn-trace-id",
            "request-id",
            "correlation-id",
        ]
        out: dict[str, str] = {}
        for k in keys:
            v = response.headers.get(k)
            if v:
                out[k] = v
        return out

    @staticmethod
    def _safe_text(response: httpx.Response, limit: int = 2000) -> str:
        try:
            t = response.text
        except Exception:
            return "<no-response-text>"
        t = t.strip()
        if len(t) > limit:
            return t[:limit] + "...(truncated)"
        return t

    @staticmethod
    def _safe_json_or_text(response: httpx.Response) -> Any:
        """
        Пытаемся распарсить JSON. Если не JSON — возвращаем строку.
        """
        try:
            return response.json()
        except Exception:
            return OzonClient._safe_text(response)

    async def _request_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Отправляет POST запрос в Ozon API и возвращает JSON как dict.

        При 4xx/5xx поднимает httpx.HTTPStatusError, но предварительно
        логирует детальную причину (включая тело ответа).
        """
        url = f"{self.BASE_URL}{path}"

        last_exc: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                timeout = httpx.Timeout(self.timeout_seconds)
                limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
                async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
                    response = await client.post(url, json=payload, headers=self._headers())

                if response.status_code >= 400:
                    ids = self._extract_request_ids(response)
                    body_any = self._safe_json_or_text(response)

                    logger.warning(
                        "Ozon API HTTP %s for %s. attempt=%s/%s request_ids=%s response_body=%s",
                        response.status_code,
                        path,
                        attempt,
                        self.max_attempts,
                        ids if ids else {},
                        body_any,
                    )

                    # Поднимаем стандартное исключение (с request/response внутри)
                    response.raise_for_status()

                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError(f"Ozon API вернул неожиданный тип JSON: {type(data)}")
                return data

            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt >= self.max_attempts:
                    logger.error(
                        "Ozon API network/timeout error for %s. attempts=%s/%s. last_error=%s",
                        path,
                        attempt,
                        self.max_attempts,
                        repr(exc),
                    )
                    raise

                delay = self.backoff_base_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Ozon API network/timeout error (attempt %s/%s). Retrying in %.1fs. Error: %s",
                    attempt,
                    self.max_attempts,
                    delay,
                    repr(exc),
                )
                await asyncio.sleep(delay)

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                # Для 4xx обычно ретраи не нужны, но бывают 429/5xx.
                status = exc.response.status_code if exc.response is not None else None

                # 429/5xx можно повторить, 400/401/403 обычно бессмысленно
                retryable = False
                if status is not None:
                    if status == 429 or 500 <= status <= 599:
                        retryable = True

                if not retryable or attempt >= self.max_attempts:
                    # Дадим максимально понятную ошибку наверх
                    resp = exc.response
                    ids = self._extract_request_ids(resp) if resp is not None else {}
                    body = self._safe_text(resp) if resp is not None else "<no-response>"
                    raise httpx.HTTPStatusError(
                        message=(
                            f"Ozon API error: HTTP {status} for {path}. "
                            f"request_ids={ids}. body={body}"
                        ),
                        request=exc.request,
                        response=exc.response,
                    ) from exc

                delay = self.backoff_base_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Ozon API HTTP error retryable (status=%s) attempt=%s/%s. Retrying in %.1fs.",
                    status,
                    attempt,
                    self.max_attempts,
                    delay,
                )
                await asyncio.sleep(delay)

            except Exception as exc:
                last_exc = exc
                logger.exception("Unexpected error in OzonClient for %s: %s", path, repr(exc))
                raise

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("OzonClient: неизвестная ошибка _request_json()")

    @staticmethod
    def _validate_limit_offset(limit: int, offset: int) -> tuple[int, int]:
        if limit <= 0 or limit > 1000:
            raise ValueError("limit должен быть в диапазоне 1..1000")
        if offset < 0:
            raise ValueError("offset должен быть >= 0")
        return limit, offset

    async def get_new_postings_fbs(
        self,
        status: str = "awaiting_packaging",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Получает список FBS posting'ов по статусу.
        API Ozon: POST /v3/posting/fbs/list

        Примечание:
        - Если получаешь 400, теперь в логах будет тело ответа,
          и станет ясно, что именно не понравилось Ozon (статус, фильтр, права, формат).
        """
        limit, offset = self._validate_limit_offset(limit, offset)

        payload: dict[str, Any] = {
            "filter": {
                "status": status,
            },
            "with": {
                "analytics_data": False,
                "financial_data": False,
            },
            "dir": "ASC",
            "limit": limit,
            "offset": offset,
        }

        data = await self._request_json(self.FBS_LIST_PATH, payload)
        result = data.get("result", {})
        postings = result.get("postings", [])

        if isinstance(postings, list):
            return postings
        return []

    async def get_new_postings_fbo(
        self,
        status: str = "awaiting_packaging",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Получает список FBO posting'ов по статусу.
        API Ozon: POST /v2/posting/fbo/list
        """
        limit, offset = self._validate_limit_offset(limit, offset)

        payload: dict[str, Any] = {
            "filter": {
                "status": status,
            },
            "with": {
                "analytics_data": False,
                "financial_data": False,
            },
            "dir": "ASC",
            "limit": limit,
            "offset": offset,
        }

        data = await self._request_json(self.FBO_LIST_PATH, payload)
        result = data.get("result", {})
        postings = result.get("postings", [])

        if isinstance(postings, list):
            return postings
        return []
