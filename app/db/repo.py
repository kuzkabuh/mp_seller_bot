"""
Версия файла: 1.0.0
Описание: Репозиторий (CRUD) для работы с БД mp_seller_bot
Дата изменения: 2025-12-27
"""

from __future__ import annotations

import datetime as dt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MarketplaceCredential, OrderEvent, User


class Repo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_user(self, tg_user_id: int, tg_username: str | None) -> User:
        q = await self.session.execute(select(User).where(User.tg_user_id == tg_user_id))
        user = q.scalar_one_or_none()
        if user:
            return user
        user = User(tg_user_id=tg_user_id, tg_username=tg_username)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def upsert_credential(self, user_id: int, marketplace: str, encrypted_api_key: str) -> MarketplaceCredential:
        q = await self.session.execute(
            select(MarketplaceCredential).where(
                MarketplaceCredential.user_id == user_id,
                MarketplaceCredential.marketplace == marketplace,
            )
        )
        cred = q.scalar_one_or_none()
        now = dt.datetime.utcnow()
        if cred:
            cred.encrypted_api_key = encrypted_api_key
            cred.is_active = True
            cred.updated_at = now
            await self.session.commit()
            await self.session.refresh(cred)
            return cred

        cred = MarketplaceCredential(
            user_id=user_id,
            marketplace=marketplace,
            encrypted_api_key=encrypted_api_key,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.session.add(cred)
        await self.session.commit()
        await self.session.refresh(cred)
        return cred

    async def list_active_credentials(self) -> list[MarketplaceCredential]:
        q = await self.session.execute(select(MarketplaceCredential).where(MarketplaceCredential.is_active == True))
        return list(q.scalars().all())

    async def deactivate_credential(self, user_id: int, marketplace: str) -> None:
        q = await self.session.execute(
            select(MarketplaceCredential).where(
                MarketplaceCredential.user_id == user_id,
                MarketplaceCredential.marketplace == marketplace,
            )
        )
        cred = q.scalar_one_or_none()
        if cred:
            cred.is_active = False
            cred.updated_at = dt.datetime.utcnow()
            await self.session.commit()

    async def insert_order_event_if_new(
        self,
        user_id: int,
        marketplace: str,
        scheme: str,
        external_id: str,
        payload_json: str,
    ) -> bool:
        exists_q = await self.session.execute(
            select(OrderEvent.id).where(
                OrderEvent.user_id == user_id,
                OrderEvent.marketplace == marketplace,
                OrderEvent.scheme == scheme,
                OrderEvent.external_id == external_id,
            )
        )
        exists = exists_q.scalar_one_or_none()
        if exists is not None:
            return False

        ev = OrderEvent(
            user_id=user_id,
            marketplace=marketplace,
            scheme=scheme,
            external_id=external_id,
            payload_json=payload_json,
        )
        self.session.add(ev)
        await self.session.commit()
        return True
