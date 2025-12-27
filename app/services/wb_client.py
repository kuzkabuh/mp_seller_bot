"""
Версия файла: 1.0.0
Описание: Клиент Wildberries API (скелет) для mp_seller_bot
Дата изменения: 2025-12-27
"""

from __future__ import annotations

import httpx


class WBClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

    async def get_new_orders_fbs(self) -> list[dict]:
        """
        Заглушка: здесь будет реальный запрос WB FBS.
        Возвращает список заказов/сборочных заданий в виде dict.
        """
        # TODO: реализовать эндпоинт WB FBS
        return []

    async def get_new_orders_fbo(self) -> list[dict]:
        """
        Заглушка: здесь будет реальный запрос WB FBO.
        """
        # TODO: реализовать эндпоинт WB FBO
        return []

    async def _get(self, url: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, headers=self._headers(), params=params)
            r.raise_for_status()
            return r.json()
