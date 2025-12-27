# Версия файла: 2.0.1
# Описание: Модуль для хранения и извлечения API-ключей маркетплейсов.
# Адаптирован для модели MarketplaceCredential и безопасного
# шифрования. Используется в старых обработчиках, где не
# применяется Repo. Сохраняет как ключи Wildberries, так и
# пару client_id + api_key для Ozon. Создаёт пользователя
# автоматически при сохранении ключей.
# Дата изменения: 2025-12-28

from __future__ import annotations

import logging
from typing import Literal, Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MarketplaceCredential, User

logger = logging.getLogger("key_store")

# Тип для идентификации маркетплейсов
Marketplace = Literal["wb", "ozon"]


def build_fernet_from_key(raw_key: str) -> Fernet:
    """
    Строит объект Fernet из текстового ключа.

    Ожидается, что raw_key — это корректный base64-ключ для Fernet
    (как в настройке FERNET_KEY). В случае некорректного ключа
    возбуждается ValueError.
    """
    key = (raw_key or "").strip().encode("utf-8")
    try:
        return Fernet(key)
    except Exception as exc:  # ValueError, TypeError и т.п.
        logger.error("Неверный FERNET_KEY в конфигурации: не удалось создать Fernet", exc_info=exc)
        raise ValueError("Invalid FERNET_KEY for Fernet") from exc


def encrypt_text(fernet: Fernet, plaintext: str) -> str:
    """
    Шифрует строку plaintext с помощью Fernet и возвращает строковый токен.
    """
    plaintext_bytes = (plaintext or "").encode("utf-8")
    token = fernet.encrypt(plaintext_bytes)
    return token.decode("utf-8")


def decrypt_text(fernet: Fernet, ciphertext: str) -> str:
    """
    Расшифровывает строку ciphertext с помощью Fernet.

    В случае некорректного токена возбуждает InvalidToken.
    """
    if ciphertext is None:
        return ""
    try:
        token_bytes = ciphertext.encode("utf-8")
        raw = fernet.decrypt(token_bytes)
        return raw.decode("utf-8")
    except InvalidToken as exc:
        logger.error("Не удалось расшифровать значение: некорректный токен", exc_info=exc)
        raise


async def ensure_user(session: AsyncSession, tg_user_id: int) -> User:
    """
    Возвращает пользователя с указанным telegram ID. Если пользователь
    отсутствует, создаёт новую запись и сохраняет её.

    :param session: текущая сессия БД
    :param tg_user_id: идентификатор пользователя в Telegram (chat_id)
    :return: ORM-объект User
    """
    q = select(User).where(User.tg_user_id == tg_user_id)
    res = await session.execute(q)
    user = res.scalar_one_or_none()
    if user is None:
        user = User(tg_user_id=tg_user_id, tg_username=None)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info("Создан новый пользователь user_id=%s tg_user_id=%s", user.id, tg_user_id)
    return user


async def upsert_wb_api_key(
    session: AsyncSession,
    tg_user_id: int,
    api_key_plain: str,
    fernet_key: str,
) -> None:
    """
    Сохраняет API-ключ Wildberries в зашифрованном виде. Если запись
    существует, обновляет ключ и активирует запись. Пользователь
    создаётся, если ранее не существовал.
    """
    user = await ensure_user(session, tg_user_id)
    fernet = build_fernet_from_key(fernet_key)
    encrypted_api = encrypt_text(fernet, api_key_plain)

    q = select(MarketplaceCredential).where(
        MarketplaceCredential.user_id == user.id,
        MarketplaceCredential.marketplace == "wb",
    )
    res = await session.execute(q)
    cred = res.scalar_one_or_none()

    if cred is None:
        cred = MarketplaceCredential(
            user_id=user.id,
            tg_user_id=tg_user_id,
            marketplace="wb",
            encrypted_api_key=encrypted_api,
            encrypted_client_id=None,
            is_active=True,
        )
        session.add(cred)
        logger.info("Создана новая запись WB credential для tg_user_id=%s", tg_user_id)
    else:
        cred.encrypted_api_key = encrypted_api
        cred.encrypted_client_id = None
        cred.is_active = True
        logger.info("Обновлён WB ключ для tg_user_id=%s", tg_user_id)

    await session.commit()
    logger.info("WB key saved for tg_user_id=%s", tg_user_id)


async def upsert_ozon_credentials(
    session: AsyncSession,
    tg_user_id: int,
    client_id_plain: str,
    api_key_plain: str,
    fernet_key: str,
) -> None:
    """
    Сохраняет пару (client_id, api_key) для Ozon. Если запись
    существует, обновляет значения и активирует её. Создаёт
    пользователя при отсутствии.
    """
    user = await ensure_user(session, tg_user_id)
    fernet = build_fernet_from_key(fernet_key)
    encrypted_api = encrypt_text(fernet, api_key_plain)
    encrypted_client = encrypt_text(fernet, client_id_plain)

    q = select(MarketplaceCredential).where(
        MarketplaceCredential.user_id == user.id,
        MarketplaceCredential.marketplace == "ozon",
    )
    res = await session.execute(q)
    cred = res.scalar_one_or_none()

    if cred is None:
        cred = MarketplaceCredential(
            user_id=user.id,
            tg_user_id=tg_user_id,
            marketplace="ozon",
            encrypted_api_key=encrypted_api,
            encrypted_client_id=encrypted_client,
            is_active=True,
        )
        session.add(cred)
        logger.info("Создана новая запись Ozon credential для tg_user_id=%s", tg_user_id)
    else:
        cred.encrypted_api_key = encrypted_api
        cred.encrypted_client_id = encrypted_client
        cred.is_active = True
        logger.info("Обновлены Ozon credentials для tg_user_id=%s", tg_user_id)

    await session.commit()
    logger.info("Ozon credentials saved for tg_user_id=%s", tg_user_id)


async def get_wb_api_key(
    session: AsyncSession,
    tg_user_id: int,
    fernet_key: str,
) -> Optional[str]:
    """
    Возвращает расшифрованный API-ключ Wildberries для пользователя,
    если он подключён и активен. В противном случае возвращает None.
    """
    q = select(MarketplaceCredential).where(
        MarketplaceCredential.tg_user_id == tg_user_id,
        MarketplaceCredential.marketplace == "wb",
        MarketplaceCredential.is_active == True,  # noqa: E712
    )
    res = await session.execute(q)
    cred = res.scalar_one_or_none()
    if cred is None:
        return None
    fernet = build_fernet_from_key(fernet_key)
    try:
        return decrypt_text(fernet, cred.encrypted_api_key)
    except InvalidToken:
        # Если по какой-то причине ключ перестал расшифровываться,
        # безопаснее вернуть None и дать пользователю переподключить.
        logger.error("Не удалось расшифровать WB ключ для tg_user_id=%s", tg_user_id)
        return None


async def get_ozon_credentials(
    session: AsyncSession,
    tg_user_id: int,
    fernet_key: str,
) -> Optional[Tuple[str, str]]:
    """
    Возвращает пару (client_id, api_key) для Ozon, если они
    подключены и активны. В противном случае возвращает None.
    """
    q = select(MarketplaceCredential).where(
        MarketplaceCredential.tg_user_id == tg_user_id,
        MarketplaceCredential.marketplace == "ozon",
        MarketplaceCredential.is_active == True,  # noqa: E712
    )
    res = await session.execute(q)
    cred = res.scalar_one_or_none()
    if cred is None or cred.encrypted_client_id is None:
        return None

    fernet = build_fernet_from_key(fernet_key)
    try:
        api_key = decrypt_text(fernet, cred.encrypted_api_key)
        client_id = decrypt_text(fernet, cred.encrypted_client_id)
    except InvalidToken:
        logger.error("Не удалось расшифровать Ozon credentials для tg_user_id=%s", tg_user_id)
        return None

    return client_id, api_key
