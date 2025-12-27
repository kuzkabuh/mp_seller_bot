# Версия файла: 1.0.0
# Описание: Репозиторий заказов и маркеров обработки
# Дата изменения: 2025-12-27

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MarketplaceAccount, Order

logger = logging.getLogger(__name__)


class OrdersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exists(self, account_id: int, marketplace_order_id: str) -> bool:
        res = await self._session.execute(
            select(Order.id).where(
                Order.marketplace_account_id == account_id,
                Order.marketplace_order_id == marketplace_order_id,
            )
        )
        return res.scalar_one_or_none() is not None

    async def add_if_not_exists(self, order: Order) -> bool:
        """Возвращает True, если заказ был добавлен (новый)."""
        self._session.add(order)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return False
        return True

    async def update_account_poll_marker(
        self,
        *,
        account_id: int,
        last_orders_check_at: dt.datetime,
        last_order_marker: str | None,
    ) -> None:
        res = await self._session.execute(select(MarketplaceAccount).where(MarketplaceAccount.id == account_id))
        account = res.scalar_one()
        account.last_orders_check_at = last_orders_check_at
        account.last_order_marker = last_order_marker

