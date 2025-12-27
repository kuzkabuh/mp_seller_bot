# Версия файла: 2.0.0
# Описание: Клиент Wildberries API для получения новых заказов.
# Реализует вызовы FBS (сборочные заказы) и заглушку для FBO.
# Дата изменения: 2025-12-27

from __future__ import annotations

import httpx
from typing import Any, Dict, List


class WBClient:
    """
    Асинхронный клиент для работы с API Wildberries.

    Для получения новых сборочных заказов FBS используется
    эндпоинт ``/api/v3/orders/new``. Для авторизации используется
    переданный API‑ключ (обычно base64 токен). Согласно
    документации WB API токен передаётся в заголовке
    ``Authorization``. Заголовок ``Content-Type`` устанавливается
    в ``application/json``.
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

    async def get_new_orders_fbs(self) -> List[Dict[str, Any]]:
        """
        Возвращает список новых FBS заказов.

        Запрос выполняется к ``https://marketplace-api.wildberries.ru/api/v3/orders/new``.
        Если метод возвращает ключ ``orders``, возвращается его
        содержимое. В противном случае возвращается пустой список.
        При ошибках запроса генерируется исключение httpx.HTTPError.
        """
        url = "https://marketplace-api.wildberries.ru/api/v3/orders/new"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers())
            response.raise_for_status()
            data = response.json()
        # Ожидаем, что успешный ответ содержит ключ orders
        orders = data.get("orders")
        if isinstance(orders, list):
            return orders
        return []

    async def get_new_orders_fbo(self) -> List[Dict[str, Any]]:
        """
        Заглушка для FBO заказов Wildberries.

        На текущий момент API Wildberries предоставляет FBS заказы
        через эндпоинт ``/api/v3/orders/new``. Когда официальный
        эндпоинт для FBO будет доступен, здесь будет реализован
        соответствующий запрос. Сейчас возвращается пустой список.
        """
        return []