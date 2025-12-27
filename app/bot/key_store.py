# Версия файла: 1.2.0
# Описание: Хранение ключей маркетплейсов (добавлена работа с client_id)
# Дата изменения: 2025-12-27

from __future__ import annotations

import logging
from typing import Literal, Optional, Tuple

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


async def upsert_wb_api_key(
    session: AsyncSession,
    tg_user_id: int,
    api_key_plain: str,
    fernet_key: str,
) -> None:
    """Сохраняет только ключ WB."""
    await ensure_user(session, tg_user_id)
    fernet = build_fernet(fernet_key)
    encrypted_api = encrypt_text(fernet, api_key_plain)

    q = select(MarketplaceAccount).where(
        MarketplaceAccount.tg_user_id == tg_user_id,
        MarketplaceAccount.marketplace == "wb",
    )
    res = await session.execute(q)
    row = res.scalar_one_or_none()

    if row is None:
        session.add(
            MarketplaceAccount(
                tg_user_id=tg_user_id,
                marketplace="wb",
                api_key_encrypted=encrypted_api,
                client_id_encrypted=None,
                is_active=True,
            )
        )
    else:
        row.api_key_encrypted = encrypted_api
        row.client_id_encrypted = None
        row.is_active = True

    await session.commit()
    logger.info("WB key saved for tg_user_id=%s", tg_user_id)


async def upsert_ozon_credentials(
    session: AsyncSession,
    tg_user_id: int,
    client_id_plain: str,
    api_key_plain: str,
    fernet_key: str,
) -> None:
    """Сохраняет client_id и api_key для Ozon."""
    await ensure_user(session, tg_user_id)
    fernet = build_fernet(fernet_key)
    encrypted_api = encrypt_text(fernet, api_key_plain)
    encrypted_client = encrypt_text(fernet, client_id_plain)

    q = select(MarketplaceAccount).where(
        MarketplaceAccount.tg_user_id == tg_user_id,
        MarketplaceAccount.marketplace == "ozon",
    )
    res = await session.execute(q)
    row = res.scalar_one_or_none()

    if row is None:
        session.add(
            MarketplaceAccount(
                tg_user_id=tg_user_id,
                marketplace="ozon",
                api_key_encrypted=encrypted_api,
                client_id_encrypted=encrypted_client,
                is_active=True,
            )
        )
    else:
        row.api_key_encrypted = encrypted_api
        row.client_id_encrypted = encrypted_client
        row.is_active = True

    await session.commit()
    logger.info("Ozon credentials saved for tg_user_id=%s", tg_user_id)


async def get_wb_api_key(
    session: AsyncSession,
    tg_user_id: int,
    fernet_key: str,
) -> Optional[str]:
    q = select(MarketplaceAccount).where(
        MarketplaceAccount.tg_user_id == tg_user_id,
        MarketplaceAccount.marketplace == "wb",
        MarketplaceAccount.is_active == True,  # noqa: E712
    )
    res = await session.execute(q)
    row = res.scalar_one_or_none()
    if row is None:
        return None
    fernet = build_fernet(fernet_key)
    return decrypt_text(fernet, row.api_key_encrypted)


async def get_ozon_credentials(
    session: AsyncSession,
    tg_user_id: int,
    fernet_key: str,
) -> Optional[Tuple[str, str]]:
    q = select(MarketplaceAccount).where(
        MarketplaceAccount.tg_user_id == tg_user_id,
        MarketplaceAccount.marketplace == "ozon",
        MarketplaceAccount.is_active == True,  # noqa: E712
    )
    res = await session.execute(q)
    row = res.scalar_one_or_none()
    if row is None or row.client_id_encrypted is None:
        return None
    fernet = build_fernet(fernet_key)
    api_key = decrypt_text(fernet, row.api_key_encrypted)
    client_id = decrypt_text(fernet, row.client_id_encrypted)
    return client_id, api_key
