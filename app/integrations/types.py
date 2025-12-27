# Версия файла: 1.0.0
# Описание: Типы данных для интеграций маркетплейсов
# Дата изменения: 2025-12-27

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class MarketplaceOrderItem(BaseModel):
    sku: str | None = None
    name: str | None = None
    quantity: int = 1
    price: float | None = None
    currency: str | None = None


class MarketplaceOrder(BaseModel):
    marketplace_order_id: str
    created_at: dt.datetime | None = None
    status: str | None = None
    warehouse: str | None = None
    total_amount: float | None = None
    currency: str | None = None
    items: list[MarketplaceOrderItem] = Field(default_factory=list)
    payload: dict = Field(default_factory=dict)


class StockItem(BaseModel):
    sku: str
    name: str | None = None
    warehouse: str | None = None
    quantity: int = 0
    payload: dict = Field(default_factory=dict)


class SalesStatItem(BaseModel):
    date: dt.date
    orders_count: int = 0
    sales_count: int = 0
    revenue: float = 0.0
    payload: dict = Field(default_factory=dict)

