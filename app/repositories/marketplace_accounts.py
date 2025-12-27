# Версия файла: 1.0.0
# Описание: Репозиторий подключенных аккаунтов маркетплейсов
# Дата изменения: 2025-12-27

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import MarketplaceAccount, MarketplaceType, NotificationSettings, User


class MarketplaceAccountsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: int) -> list[MarketplaceAccount]:
        res = await self._session.execute(
            select(MarketplaceAccount)
            .where(MarketplaceAccount.user_id == user_id)
            .options(selectinload(MarketplaceAccount.notification_settings))
            .order_by(MarketplaceAccount.id.asc())
        )
        return list(res.scalars().all())

    async def get_by_user_and_type(self, user_id: int, mp: MarketplaceType) -> MarketplaceAccount | None:
        res = await self._session.execute(
            select(MarketplaceAccount)
            .where(MarketplaceAccount.user_id == user_id, MarketplaceAccount.marketplace_type == mp)
            .options(selectinload(MarketplaceAccount.notification_settings))
        )
        return res.scalar_one_or_none()

    async def upsert_account(
        self,
        *,
        user_id: int,
        mp: MarketplaceType,
        api_key: str,
        client_id: str | None,
        is_active: bool = True,
    ) -> MarketplaceAccount:
        account = await self.get_by_user_and_type(user_id, mp)
        if account is None:
            account = MarketplaceAccount(
                user_id=user_id,
                marketplace_type=mp,
                api_key=api_key,
                client_id=client_id,
                is_active=is_active,
                last_orders_check_at=dt.datetime.now(dt.timezone.utc),
                last_order_marker=None,
            )
            self._session.add(account)
            await self._session.flush()
            account.notification_settings = NotificationSettings(
                marketplace_account_id=account.id,
                notify_new_orders=True,
                daily_summary_enabled=False,
                low_stock_alert_enabled=False,
            )
            await self._session.flush()
            return account

        account.api_key = api_key
        account.client_id = client_id
        account.is_active = is_active
        if account.notification_settings is None:
            account.notification_settings = NotificationSettings(
                marketplace_account_id=account.id,
                notify_new_orders=True,
                daily_summary_enabled=False,
                low_stock_alert_enabled=False,
            )
        return account

    async def delete_account(self, *, user_id: int, mp: MarketplaceType) -> bool:
        account = await self.get_by_user_and_type(user_id, mp)
        if account is None:
            return False
        await self._session.delete(account)
        return True

    async def set_notifications(
        self,
        *,
        account_id: int,
        notify_new_orders: bool | None = None,
        daily_summary_enabled: bool | None = None,
        low_stock_alert_enabled: bool | None = None,
    ) -> None:
        res = await self._session.execute(
            select(MarketplaceAccount)
            .where(MarketplaceAccount.id == account_id)
            .options(selectinload(MarketplaceAccount.notification_settings))
        )
        account = res.scalar_one()
        if account.notification_settings is None:
            account.notification_settings = NotificationSettings(marketplace_account_id=account.id)
        ns = account.notification_settings
        if notify_new_orders is not None:
            ns.notify_new_orders = notify_new_orders
        if daily_summary_enabled is not None:
            ns.daily_summary_enabled = daily_summary_enabled
        if low_stock_alert_enabled is not None:
            ns.low_stock_alert_enabled = low_stock_alert_enabled

    async def list_active_for_polling(self) -> list[MarketplaceAccount]:
        res = await self._session.execute(
            select(MarketplaceAccount)
            .where(MarketplaceAccount.is_active.is_(True))
            .options(
                selectinload(MarketplaceAccount.user),
                selectinload(MarketplaceAccount.notification_settings),
            )
            .order_by(MarketplaceAccount.id.asc())
        )
        return list(res.scalars().all())


async def ensure_user(session: AsyncSession, telegram_id: int, username: str | None, full_name: str | None) -> User:
    """Утилита: гарантировать наличие пользователя (используется хендлерами)."""
    from app.repositories.users import UsersRepository

    repo = UsersRepository(session)
    return await repo.get_or_create(telegram_id=telegram_id, username=username, full_name=full_name)
