# Версия файла: 1.0.0
# Описание: Интеграция с Ozon Seller API
# Дата изменения: 2025-12-27

from __future__ import annotations

import datetime as dt
from collections import defaultdict

from app.integrations.base import BaseAPIClient, MarketplaceAPIError
from app.integrations.types import MarketplaceOrder, MarketplaceOrderItem, SalesStatItem, StockItem


class OzonAPI(BaseAPIClient):
    """
    Ozon Seller API.

    Документация: https://docs.ozon.ru/api/seller/
    """

    def __init__(self, *, api_key: str, client_id: str) -> None:
        api_key = api_key.strip()
        client_id = client_id.strip()
        if not client_id:
            raise MarketplaceAPIError("Для Ozon требуется client_id")
        super().__init__(
            base_url="https://api-seller.ozon.ru",
            headers={"Api-Key": api_key, "Client-Id": client_id},
        )

    @staticmethod
    def _to_iso(dt_value: dt.datetime) -> str:
        if dt_value.tzinfo is None:
            dt_value = dt_value.replace(tzinfo=dt.timezone.utc)
        return dt_value.isoformat()

    async def get_new_orders(self, *, since: dt.datetime, limit: int = 50) -> list[MarketplaceOrder]:
        """
        Получение новых отправлений (postings) FBS.
        В реальных сценариях можно расширить на FBO/realFBS и статусы.
        """
        to_dt = dt.datetime.now(dt.timezone.utc)
        payload = {
            "filter": {
                "since": self._to_iso(since),
                "to": self._to_iso(to_dt),
                "status": "",  # пусто => все
            },
            "limit": int(limit),
            "offset": 0,
            "with": {
                "analytics_data": True,
                "financial_data": True,
                "barcodes": True,
                "translit": False,
            },
        }
        data = await self._request_json("POST", "/v3/posting/fbs/list", json=payload)
        if not isinstance(data, dict):
            return []
        result = data.get("result") or {}
        postings = result.get("postings") or []
        if not isinstance(postings, list):
            return []

        out: list[MarketplaceOrder] = []
        for p in postings:
            if not isinstance(p, dict):
                continue
            mp_order_id = str(p.get("posting_number") or "").strip()
            if not mp_order_id:
                continue

            created_at = None
            created_str = p.get("in_process_at") or p.get("created_at")
            if isinstance(created_str, str):
                try:
                    created_at = dt.datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                except Exception:
                    created_at = None

            items_raw = p.get("products") or []
            items: list[MarketplaceOrderItem] = []
            if isinstance(items_raw, list):
                for it in items_raw:
                    if not isinstance(it, dict):
                        continue
                    items.append(
                        MarketplaceOrderItem(
                            sku=str(it.get("sku") or it.get("offer_id") or ""),
                            name=it.get("name") or it.get("offer_id") or None,
                            quantity=int(it.get("quantity") or 1),
                            price=float(it.get("price") or 0) or None,
                            currency="RUB",
                        )
                    )

            total_amount = None
            fin = p.get("financial_data") or {}
            if isinstance(fin, dict):
                try:
                    total_amount = float((fin.get("products") or [{}])[0].get("price") or 0) or None
                except Exception:
                    total_amount = None

            out.append(
                MarketplaceOrder(
                    marketplace_order_id=mp_order_id,
                    created_at=created_at,
                    status=p.get("status") or None,
                    warehouse=(p.get("warehouse_id") and str(p.get("warehouse_id"))) or None,
                    total_amount=total_amount,
                    currency="RUB",
                    items=items,
                    payload=p,
                )
            )
        out.sort(key=lambda x: x.created_at or dt.datetime.min.replace(tzinfo=dt.timezone.utc))
        return out

    async def get_stocks(self, *, limit: int = 1000, offset: int = 0) -> list[StockItem]:
        """
        Остатки по товарам.
        Метод работает в зависимости от прав/типа аккаунта; при необходимости расширяется фильтрами.
        """
        payload = {
            "filter": {
                "offer_id": [],
                "product_id": [],
                "visibility": "ALL",
            },
            "limit": int(limit),
            "offset": int(offset),
        }
        data = await self._request_json("POST", "/v3/product/info/stocks", json=payload)
        if not isinstance(data, dict):
            return []
        result = data.get("result") or {}
        items = result.get("items") or []
        if not isinstance(items, list):
            return []

        out: list[StockItem] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            offer_id = str(it.get("offer_id") or it.get("sku") or it.get("product_id") or "").strip()
            if not offer_id:
                continue
            stocks = it.get("stocks") or []
            qty = 0
            if isinstance(stocks, list):
                for s in stocks:
                    if not isinstance(s, dict):
                        continue
                    qty += int(s.get("present") or 0)
            out.append(
                StockItem(
                    sku=offer_id,
                    name=it.get("name") or None,
                    warehouse=None,
                    quantity=qty,
                    payload=it,
                )
            )
        return out

    async def get_sales_stats(self, *, date_from: dt.date, date_to: dt.date) -> list[SalesStatItem]:
        """
        Аналитика продаж по дням.
        """
        payload = {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "metrics": ["revenue", "ordered_units", "orders"],
            "dimension": ["day"],
            "filters": [],
            "sort": [{"key": "day", "order": "ASC"}],
            "limit": 1000,
            "offset": 0,
        }
        data = await self._request_json("POST", "/v1/analytics/data", json=payload)
        if not isinstance(data, dict):
            return []
        result = data.get("result") or {}
        rows = result.get("data") or []
        if not isinstance(rows, list):
            return []

        out: list[SalesStatItem] = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            dims = r.get("dimensions") or []
            metrics = r.get("metrics") or []
            if not dims or not isinstance(dims, list):
                continue
            day_str = None
            if isinstance(dims[0], dict):
                day_str = dims[0].get("id") or dims[0].get("value")
            if not isinstance(day_str, str):
                continue
            try:
                day = dt.date.fromisoformat(day_str[:10])
            except Exception:
                continue
            revenue = float(metrics[0]) if len(metrics) > 0 and metrics[0] is not None else 0.0
            ordered_units = int(metrics[1]) if len(metrics) > 1 and metrics[1] is not None else 0
            orders = int(metrics[2]) if len(metrics) > 2 and metrics[2] is not None else 0
            out.append(
                SalesStatItem(
                    date=day,
                    orders_count=orders,
                    sales_count=ordered_units,
                    revenue=revenue,
                    payload=r,
                )
            )
        return out
