# Версия файла: 1.1.0
# Описание: Сервис хранения ключей маркетплейсов (шифрование в БД)
# Дата изменения: 2025-12-27

from __future__ import annotations

import logging
from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MarketplaceAccount, User
from security.crypto import build_fernet, decrypt_text, encrypt_text

logger = logging.getLogger("key_store")

Marketplace = Literal["wb", "ozon"]


async def ensure_user(session: AsyncSession, tg_user_id: int) -> None:
    q = select(User).where(User.tg_user_id == tg_user_id)
    res = await session.execute(q)
    user = res.scalar_one_or_none()
    if user is None:
        session.add(User(tg_user_id=tg_user_id))
        await session.commit()


async def upsert_api_key(
    session: AsyncSession,
    tg_user_id: int,
    marketplace: Marketplace,
    api_key_plain: str,
    fernet_key: str,
) -> None:
    await ensure_user(session, tg_user_id)

    fernet = build_fernet(fernet_key)
    encrypted = encrypt_text(fernet, api_key_plain)

    q = select(MarketplaceAccount).where(
        MarketplaceAccount.tg_user_id == tg_user_id,
        MarketplaceAccount.marketplace == marketplace,
    )
    res = await session.execute(q)
    row = res.scalar_one_or_none()

    if row is None:
        session.add(MarketplaceAccount(tg_user_id=tg_user_id, marketplace=marketplace, api_key_encrypted=encrypted))
    else:
        row.api_key_encrypted = encrypted

    await session.commit()
    logger.info("API key saved for tg_user_id=%s marketplace=%s", tg_user_id, marketplace)


async def get_api_key(
    session: AsyncSession,
    tg_user_id: int,
    marketplace: Marketplace,
    fernet_key: str,
) -> Optional[str]:
    q = select(MarketplaceAccount).where(
        MarketplaceAccount.tg_user_id == tg_user_id,
        MarketplaceAccount.marketplace == marketplace,
    )
    res = await session.execute(q)
    row = res.scalar_one_or_none()
    if row is None:
        return None

    fernet = build_fernet(fernet_key)
    return decrypt_text(fernet, row.api_key_encrypted)
