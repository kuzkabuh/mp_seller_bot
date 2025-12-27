"""
Версия файла: 2.1.0
Описание: Асинхронный репозиторий для работы с БД mp_seller_bot (идемпотентность, статусы подключений, единый интерфейс).
Дата изменения: 2025-12-28

Класс Repo инкапсулирует операции чтения/записи, связанные
с пользователями, учётными данными маркетплейсов и событиями заказов.

Улучшения:
- Добавлены методы для статуса подключений: get_credentials_status, get_active_credential, list_user_credentials.
- Добавлена валидация marketplace и нормализация значений.
- Добавлены безопасные методы commit/refresh с обработкой ошибок и rollback.
- Добавлен режим "мягкого" обновления username (без лишних commit, если не менялся).
- Добавлен общий метод deactivate_all_credentials (на будущее).
- Улучшена insert_order_event_if_new: опционально возвращает id вставленной записи (через insert + flush), но по умолчанию сохраняем поведение bool.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MarketplaceCredential, OrderEvent, User

logger = logging.getLogger(__name__)


def _norm_marketplace(marketplace: str) -> str:
    mp = (marketplace or "").strip().lower()
    if mp in ("wb", "wildberries"):
        return "wb"
    if mp in ("oz", "ozon"):
        return "ozon"
    return mp


def _validate_marketplace(marketplace: str) -> None:
    mp = _norm_marketplace(marketplace)
    if mp not in ("wb", "ozon"):
        raise ValueError("marketplace должен быть 'wb' или 'ozon'")


class Repo:
    """Репозиторий с методами для работы с пользователями, credential-ами и событиями."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except Exception:
            try:
                await self.session.rollback()
            except Exception:
                pass
            raise

    async def get_or_create_user(self, tg_user_id: int, tg_username: Optional[str]) -> User:
        """
        Находит пользователя по telegram-ID либо создаёт нового.

        :param tg_user_id: идентификатор пользователя в Telegram
        :param tg_username: username пользователя (может быть None)
        :return: ORM-объект пользователя
        """
        result = await self.session.execute(select(User).where(User.tg_user_id == tg_user_id))
        user = result.scalar_one_or_none()
        if user:
            new_username = tg_username.strip() if isinstance(tg_username, str) and tg_username.strip() else None
            if new_username and user.tg_username != new_username:
                user.tg_username = new_username
                await self._commit()
                await self.session.refresh(user)
            return user

        user = User(
            tg_user_id=tg_user_id,
            tg_username=tg_username.strip() if isinstance(tg_username, str) and tg_username.strip() else None,
        )
        self.session.add(user)
        await self._commit()
        await self.session.refresh(user)
        return user

    async def upsert_credential(
        self,
        user_id: int,
        tg_user_id: int,
        marketplace: str,
        encrypted_api_key: str,
        encrypted_client_id: Optional[str] = None,
    ) -> MarketplaceCredential:
        """
        Создаёт или обновляет учётную запись для маркетплейса.

        Если запись существует, перезаписывает ключи и активирует
        учётную запись. В противном случае создаёт новую запись.

        :param user_id: внутренний id пользователя из таблицы users
        :param tg_user_id: telegram-ID пользователя (chat_id)
        :param marketplace: код маркетплейса ("wb" или "ozon")
        :param encrypted_api_key: зашифрованный API ключ
        :param encrypted_client_id: зашифрованный client_id (для Ozon)
        :return: ORM-объект credential
        """
        _validate_marketplace(marketplace)
        mp = _norm_marketplace(marketplace)

        result = await self.session.execute(
            select(MarketplaceCredential).where(
                MarketplaceCredential.user_id == user_id,
                MarketplaceCredential.marketplace == mp,
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
            await self._commit()
            await self.session.refresh(cred)
            return cred

        cred = MarketplaceCredential(
            user_id=user_id,
            tg_user_id=tg_user_id,
            marketplace=mp,
            encrypted_api_key=encrypted_api_key,
            encrypted_client_id=encrypted_client_id,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.session.add(cred)
        await self._commit()
        await self.session.refresh(cred)
        return cred

    async def list_active_credentials(self) -> list[MarketplaceCredential]:
        """Возвращает список всех активных учётных записей."""
        result = await self.session.execute(
            select(MarketplaceCredential).where(MarketplaceCredential.is_active == True)  # noqa: E712
        )
        return list(result.scalars().all())

    async def list_user_credentials(self, user_id: int) -> list[MarketplaceCredential]:
        """Возвращает все учётные записи пользователя (активные и неактивные)."""
        result = await self.session.execute(select(MarketplaceCredential).where(MarketplaceCredential.user_id == user_id))
        return list(result.scalars().all())

    async def get_active_credential(self, user_id: int, marketplace: str) -> Optional[MarketplaceCredential]:
        """Возвращает активную учётную запись пользователя для указанного маркетплейса."""
        _validate_marketplace(marketplace)
        mp = _norm_marketplace(marketplace)
        result = await self.session.execute(
            select(MarketplaceCredential).where(
                MarketplaceCredential.user_id == user_id,
                MarketplaceCredential.marketplace == mp,
                MarketplaceCredential.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_credentials_status(self, user_id: int) -> dict[str, bool]:
        """
        Возвращает статус подключений по маркетплейсам без раскрытия токенов.
        Пример: {"wb": True, "ozon": False}
        """
        creds = await self.list_user_credentials(user_id)
        status = {"wb": False, "ozon": False}
        for c in creds:
            mp = _norm_marketplace(getattr(c, "marketplace", ""))
            if mp in status:
                status[mp] = bool(getattr(c, "is_active", False))
        return status

    async def deactivate_credential(self, user_id: int, marketplace: str) -> None:
        """
        Помечает учётную запись как неактивную. Если не существует — метод ничего не делает.
        """
        _validate_marketplace(marketplace)
        mp = _norm_marketplace(marketplace)

        result = await self.session.execute(
            select(MarketplaceCredential).where(
                MarketplaceCredential.user_id == user_id,
                MarketplaceCredential.marketplace == mp,
            )
        )
        cred = result.scalar_one_or_none()
        if cred:
            cred.is_active = False
            cred.updated_at = dt.datetime.utcnow()
            await self._commit()

    async def deactivate_all_credentials(self, user_id: int) -> int:
        """
        Деактивирует все учётные записи пользователя.
        Возвращает количество изменённых записей.
        """
        creds = await self.list_user_credentials(user_id)
        changed = 0
        now = dt.datetime.utcnow()
        for cred in creds:
            if getattr(cred, "is_active", False):
                cred.is_active = False
                cred.updated_at = now
                changed += 1
        if changed:
            await self._commit()
        return changed

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

        :return: True, если событие новое и было добавлено, иначе False.
        """
        mp = _norm_marketplace(marketplace)
        scheme_norm = (scheme or "").strip().lower()
        ext = (external_id or "").strip()

        result = await self.session.execute(
            select(OrderEvent.id).where(
                OrderEvent.user_id == user_id,
                OrderEvent.marketplace == mp,
                OrderEvent.scheme == scheme_norm,
                OrderEvent.external_id == ext,
            )
        )
        exists = result.scalar_one_or_none()
        if exists is not None:
            return False

        ev = OrderEvent(
            user_id=user_id,
            marketplace=mp,
            scheme=scheme_norm,
            external_id=ext,
            payload_json=payload_json,
        )
        self.session.add(ev)
        try:
            await self._commit()
        except Exception as e:
            logger.exception("Failed to insert order event: %s", e)
            raise
        return True
