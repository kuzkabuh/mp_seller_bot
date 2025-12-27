"""
Версия файла: 2.0.0
Описание: Асинхронный репозиторий для работы с БД mp_seller_bot.

Класс ``Repo`` инкапсулирует операции чтения/записи, связанные
с пользователями, учётными данными маркетплейсов и событиями
заказов. Благодаря этому слой бота остаётся простым и
тестируемым.
Дата изменения: 2025-12-27
"""

from __future__ import annotations

import datetime as dt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MarketplaceCredential, OrderEvent, User


class Repo:
    """Репозиторий с методами для работы с пользователями и credential'ами."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_user(self, tg_user_id: int, tg_username: str | None) -> User:
        """
        Находит пользователя по telegram‑ID либо создаёт нового.

        :param tg_user_id: идентификатор пользователя в Telegram
        :param tg_username: username пользователя (может быть None)
        :return: ORM‑объект пользователя
        """
        result = await self.session.execute(select(User).where(User.tg_user_id == tg_user_id))
        user = result.scalar_one_or_none()
        if user:
            # обновляем username, если он изменился
            if tg_username and user.tg_username != tg_username:
                user.tg_username = tg_username
                await self.session.commit()
            return user
        user = User(tg_user_id=tg_user_id, tg_username=tg_username)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def upsert_credential(
        self,
        user_id: int,
        tg_user_id: int,
        marketplace: str,
        encrypted_api_key: str,
        encrypted_client_id: str | None = None,
    ) -> MarketplaceCredential:
        """
        Создаёт или обновляет учётную запись для маркетплейса.

        Если запись существует, перезаписывает ключи и активирует
        учётную запись. В противном случае создаёт новую запись.

        :param user_id: внутренний id пользователя из таблицы users
        :param tg_user_id: telegram‑ID пользователя (chat_id)
        :param marketplace: код маркетплейса ("wb" или "ozon")
        :param encrypted_api_key: зашифрованный API ключ
        :param encrypted_client_id: зашифрованный client_id (для Ozon)
        :return: ORM‑объект credential
        """
        result = await self.session.execute(
            select(MarketplaceCredential).where(
                MarketplaceCredential.user_id == user_id,
                MarketplaceCredential.marketplace == marketplace,
            )
        )
        cred = result.scalar_one_or_none()
        now = dt.datetime.utcnow()
        if cred:
            cred.encrypted_api_key = encrypted_api_key
            cred.encrypted_client_id = encrypted_client_id
            cred.is_active = True
            cred.updated_at = now
            cred.tg_user_id = tg_user_id
            await self.session.commit()
            await self.session.refresh(cred)
            return cred

        cred = MarketplaceCredential(
            user_id=user_id,
            tg_user_id=tg_user_id,
            marketplace=marketplace,
            encrypted_api_key=encrypted_api_key,
            encrypted_client_id=encrypted_client_id,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.session.add(cred)
        await self.session.commit()
        await self.session.refresh(cred)
        return cred

    async def list_active_credentials(self) -> list[MarketplaceCredential]:
        """Возвращает список всех активных учётных записей."""
        result = await self.session.execute(
            select(MarketplaceCredential).where(MarketplaceCredential.is_active == True)  # noqa: E712
        )
        return list(result.scalars().all())

    async def deactivate_credential(self, user_id: int, marketplace: str) -> None:
        """
        Помечает учётную запись как неактивную. Если не существует –
        метод ничего не делает.
        """
        result = await self.session.execute(
            select(MarketplaceCredential).where(
                MarketplaceCredential.user_id == user_id,
                MarketplaceCredential.marketplace == marketplace,
            )
        )
        cred = result.scalar_one_or_none()
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
        """
        Вставляет событие заказа, если оно ещё не было записано.

        :return: ``True``, если событие новое и было добавлено, иначе ``False``.
        """
        result = await self.session.execute(
            select(OrderEvent.id).where(
                OrderEvent.user_id == user_id,
                OrderEvent.marketplace == marketplace,
                OrderEvent.scheme == scheme,
                OrderEvent.external_id == external_id,
            )
        )
        exists = result.scalar_one_or_none()
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