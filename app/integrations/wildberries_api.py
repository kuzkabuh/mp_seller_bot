# Версия файла: 1.0.0
# Описание: Интеграция с Wildberries (официальные API статистики)
# Дата изменения: 2025-12-27

from __future__ import annotations

import datetime as dt
from collections import defaultdict

from app.integrations.base import BaseAPIClient
from app.integrations.types import MarketplaceOrder, MarketplaceOrderItem, SalesStatItem, StockItem


class WildberriesAPI(BaseAPIClient):
    """
    Официальный API WB (statistics-api.wildberries.ru).

    Документация: https://openapi.wildberries.ru/
    """

    def __init__(self, api_key: str) -> None:
        super().__init__(
            base_url="https://statistics-api.wildberries.ru",
            headers={"Authorization": api_key.strip()},
        )

    @staticmethod
    def _to_rfc3339(dt_value: dt.datetime) -> str:
        if dt_value.tzinfo is None:
            dt_value = dt_value.replace(tzinfo=dt.timezone.utc)
        return dt_value.isoformat()

    async def get_new_orders(self, *, since: dt.datetime) -> list[MarketplaceOrder]:
        """
        Возвращает список заказов WB начиная с момента since.
        WB-метод отдаёт и "старые", поэтому фильтруем по createdAt.
        """
        data = await self._request_json(
            "GET",
            "/api/v1/supplier/orders",
            params={"dateFrom": self._to_rfc3339(since), "flag": 0},
        )
        if not isinstance(data, list):
            return []

        out: list[MarketplaceOrder] = []
        for raw in data:
            if not isinstance(raw, dict):
                continue
            created_at = None
            created_str = raw.get("date") or raw.get("createdAt") or raw.get("lastChangeDate")
            if isinstance(created_str, str):
                try:
                    created_at = dt.datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                except Exception:
                    created_at = None

            mp_order_id = (
                str(raw.get("odid") or raw.get("srid") or raw.get("gNumber") or raw.get("orderId") or "")
            ).strip()
            if not mp_order_id:
                continue

            items = [
                MarketplaceOrderItem(
                    sku=str(raw.get("nmId") or raw.get("supplierArticle") or raw.get("barcode") or ""),
                    name=raw.get("subject") or raw.get("brand") or None,
                    quantity=int(raw.get("quantity") or 1),
                    price=float(raw.get("totalPrice") or raw.get("priceWithDisc") or raw.get("finishedPrice") or 0)
                    or None,
                    currency="RUB",
                )
            ]

            out.append(
                MarketplaceOrder(
                    marketplace_order_id=mp_order_id,
                    created_at=created_at,
                    status=raw.get("status") or raw.get("orderType") or None,
                    warehouse=raw.get("warehouseName") or raw.get("warehouse") or None,
                    total_amount=float(raw.get("finishedPrice") or raw.get("totalPrice") or 0) or None,
                    currency="RUB",
                    items=items,
                    payload=raw,
                )
            )

        out.sort(key=lambda x: x.created_at or dt.datetime.min.replace(tzinfo=dt.timezone.utc))
        return out

    async def get_orders_by_period(self, *, date_from: dt.datetime, date_to: dt.datetime) -> list[MarketplaceOrder]:
        orders = await self.get_new_orders(since=date_from)
        out: list[MarketplaceOrder] = []
        for o in orders:
            if o.created_at is None:
                continue
            if date_from <= o.created_at <= date_to:
                out.append(o)
        return out

    async def get_stocks(self, *, since: dt.datetime | None = None) -> list[StockItem]:
        params = {}
        if since is not None:
            params["dateFrom"] = self._to_rfc3339(since)
        data = await self._request_json("GET", "/api/v1/supplier/stocks", params=params or None)
        if not isinstance(data, list):
            return []

        out: list[StockItem] = []
        for raw in data:
            if not isinstance(raw, dict):
                continue
            sku = str(raw.get("nmId") or raw.get("supplierArticle") or raw.get("barcode") or "").strip()
            if not sku:
                continue
            out.append(
                StockItem(
                    sku=sku,
                    name=raw.get("subject") or raw.get("brand") or None,
                    warehouse=raw.get("warehouseName") or None,
                    quantity=int(raw.get("quantity") or raw.get("quantityFull") or 0),
                    payload=raw,
                )
            )
        return out

    async def get_sales_stats(self, *, date_from: dt.datetime) -> list[SalesStatItem]:
        data = await self._request_json(
            "GET",
            "/api/v1/supplier/sales",
            params={"dateFrom": self._to_rfc3339(date_from), "flag": 0},
        )
        if not isinstance(data, list):
            return []

        by_day_orders: dict[dt.date, int] = defaultdict(int)
        by_day_sales: dict[dt.date, int] = defaultdict(int)
        by_day_revenue: dict[dt.date, float] = defaultdict(float)
        by_day_payloads: dict[dt.date, list[dict]] = defaultdict(list)

        for raw in data:
            if not isinstance(raw, dict):
                continue
            created_str = raw.get("date") or raw.get("lastChangeDate") or raw.get("createdAt")
            if not isinstance(created_str, str):
                continue
            try:
                dttm = dt.datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except Exception:
                continue
            day = dttm.date()
            by_day_orders[day] += 1
            by_day_sales[day] += int(raw.get("quantity") or 1)
            by_day_revenue[day] += float(raw.get("finishedPrice") or raw.get("totalPrice") or 0.0)
            by_day_payloads[day].append(raw)

        out: list[SalesStatItem] = []
        for day in sorted(by_day_orders.keys()):
            out.append(
                SalesStatItem(
                    date=day,
                    orders_count=by_day_orders[day],
                    sales_count=by_day_sales[day],
                    revenue=by_day_revenue[day],
                    payload={"items": by_day_payloads[day]},
                )
            )
        return out
