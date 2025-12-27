"""
Версия файла: 1.1.0
Описание: Реализация методов Ozon API (FBS/FBO postings)
Дата изменения: 2025-12-27

Клиент ``OzonClient`` реализует запросы к API Ozon для получения
FBS и FBO posting'ов. Для каждого запроса используются заголовки
``Api-Key`` и ``Client-Id``. Этот класс используется воркером
notifier для получения новых отправлений.
"""

from __future__ import annotations

import httpx
from typing import Any, List


class OzonClient:
    def __init__(self, api_key: str, client_id: str) -> None:
        self.api_key = api_key
        self.client_id = client_id

    def _headers(self) -> dict[str, str]:
        return {
            "Api-Key": self.api_key,
            "Client-Id": self.client_id,
            "Content-Type": "application/json",
        }

    async def get_new_postings_fbs(self) -> List[dict[str, Any]]:
        """
        Получает список новых FBS posting'ов со статусом awaiting_packaging.
        API Ozon: POST /v3/posting/fbs/list
        """
        url = "https://api-seller.ozon.ru/v3/posting/fbs/list"
        payload = {
            "filter": {
                "status": "awaiting_packaging",
            },
            "with": {
                "analytics_data": False,
                "financial_data": False,
            },
            "dir": "ASC",
            "limit": 50,
            "offset": 0,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=self._headers())
            response.raise_for_status()
            data = response.json()
        return data.get("result", {}).get("postings", [])

    async def get_new_postings_fbo(self) -> List[dict[str, Any]]:
        """
        Получает список новых FBO posting'ов.
        API Ozon: POST /v2/posting/fbo/list
        """
        url = "https://api-seller.ozon.ru/v2/posting/fbo/list"
        payload = {
            "filter": {
                "status": "awaiting_packaging",
            },
            "with": {
                "analytics_data": False,
                "financial_data": False,
            },
            "dir": "ASC",
            "limit": 50,
            "offset": 0,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=self._headers())
            response.raise_for_status()
            data = response.json()
        return data.get("result", {}).get("postings", [])