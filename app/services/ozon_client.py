"""
Версия файла: 1.0.0
Описание: Клиент Ozon Seller API (скелет) для mp_seller_bot
Дата изменения: 2025-12-27
"""

from __future__ import annotations

import httpx


class OzonClient:
    def __init__(self, api_key: str, client_id: str | None = None):
        self.api_key = api_key
        self.client_id = client_id

    def _headers(self) -> dict[str, str]:
        headers = {
            "Api-Key": self.api_key,
            "Content-Type": "application/json",
        }
        if self.client_id:
            headers["Client-Id"] = self.client_id
        return headers

    async def get_new_postings_fbs(self) -> list[dict]:
        """
        Заглушка: Ozon FBS postings.
        """
        # TODO: реализовать эндпоинт Ozon postings FBS
        return []

    async def get_new_postings_fbo(self) -> list[dict]:
        """
        Заглушка: Ozon FBO postings.
        """
        # TODO: реализовать эндпоинт Ozon postings FBO
        return []

    async def _post(self, url: str, json_body: dict) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, headers=self._headers(), json=json_body)
            r.raise_for_status()
            return r.json()
