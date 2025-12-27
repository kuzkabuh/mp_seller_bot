# Версия файла: 1.0.0
# Описание: Базовые классы/ошибки для интеграций маркетплейсов
# Дата изменения: 2025-12-27

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class MarketplaceAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class HttpConfig:
    timeout_seconds: float = 15.0
    max_retries: int = 3


class BaseAPIClient:
    def __init__(self, *, base_url: str, headers: dict[str, str], http: HttpConfig | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = headers
        self._http = http or HttpConfig()

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=httpx.Timeout(self._http.timeout_seconds),
        )

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        async with self._client() as client:
            resp = await client.request(method, url, **kwargs)
        return resp

    async def _request_json(self, method: str, url: str, **kwargs) -> dict | list:
        try:
            resp = await self._request(method, url, **kwargs)
        except httpx.TimeoutException as e:
            raise MarketplaceAPIError(f"Таймаут запроса к API: {self._base_url}{url}") from e
        except httpx.NetworkError as e:
            raise MarketplaceAPIError(f"Сетевая ошибка запроса к API: {self._base_url}{url}") from e

        if resp.status_code >= 400:
            msg = f"HTTP {resp.status_code} при запросе {self._base_url}{url}"
            try:
                data = resp.json()
            except Exception:
                data = None
            if data is not None:
                msg += f" | ответ: {data}"
            raise MarketplaceAPIError(msg)

        try:
            return resp.json()
        except Exception as e:
            raise MarketplaceAPIError("Не удалось разобрать JSON-ответ API") from e
