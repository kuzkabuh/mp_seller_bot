# Версия файла: 1.0.0
# Описание: Репозиторий пользователей
# Дата изменения: 2025-12-27

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UsersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        res = await self._session.execute(select(User).where(User.telegram_id == telegram_id))
        return res.scalar_one_or_none()

    async def get_or_create(
        self,
        telegram_id: int,
        username: str | None,
        full_name: str | None,
    ) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user is not None:
            # Поддерживаем актуальность профиля
            user.username = username
            user.full_name = full_name
            return user
        user = User(telegram_id=telegram_id, username=username, full_name=full_name)
        self._session.add(user)
        await self._session.flush()
        return user
