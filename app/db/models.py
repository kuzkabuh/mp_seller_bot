# Версия файла: 2.0.0
# Описание: ORM‑модели для mp_seller_bot. Представляет пользователей,
# учётные записи маркетплейсов и события заказов. Модели
# отражают таблицы в базе данных Postgres. Для каждого
# пользователя хранится telegram‑идентификатор и имя
# пользователя, учётные записи связывают пользователя с
# маркетплейсом (Wildberries или Ozon) и содержат
# зашифрованные ключи. События заказов фиксируются для
# предотвращения повторных уведомлений.
# Дата изменения: 2025-12-27

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class User(Base):
    """
    Пользователь Telegram. Каждому пользователю бот сохраняет
    внутренний идентификатор, telegram ID и имя пользователя.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: Уникальный идентификатор пользователя в Telegram (chat_id)
    tg_user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    #: Username в Telegram, если доступен
    tg_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Дата создания записи
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MarketplaceCredential(Base):
    """
    Учётные данные для подключения к маркетплейсам.

    Для Wildberries требуется только API ключ, поэтому поле
    ``encrypted_client_id`` будет ``NULL``. Для Ozon нужны
    ``client_id`` и ``api_key``. В целях безопасности оба
    значения сохраняются в зашифрованном виде. Поле
    ``tg_user_id`` дублирует Telegram‑ID для быстрого
    отправления уведомлений без дополнительных запросов.
    """

    __tablename__ = "marketplace_credentials"
    __table_args__ = (
        UniqueConstraint("user_id", "marketplace", name="uq_user_marketplace"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: Внешний ключ на пользователя (User.id)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    #: Telegram ID пользователя для отправки сообщений
    tg_user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    #: Код маркетплейса: ``"wb"`` или ``"ozon"``
    marketplace: Mapped[str] = mapped_column(String(16), nullable=False)
    #: Зашифрованный API ключ
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    #: Зашифрованный client_id (для Ozon), ``NULL`` для WB
    encrypted_client_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Флаг активности. Деактивация позволяет временно отключить мониторинг
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    #: Дата создания записи
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    #: Дата последнего обновления записи
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class OrderEvent(Base):
    """
    Событие заказа. Каждая запись соответствует одному
    поступлению заказа/отправления. Используется для
    дедупликации уведомлений – если комбинация
    ``user_id``, ``marketplace``, ``scheme`` и ``external_id`` уже
    существует, бот не отправляет повторное уведомление.
    """

    __tablename__ = "order_events"
    __table_args__ = (
        UniqueConstraint("user_id", "marketplace", "scheme", "external_id", name="uq_user_marketplace_scheme_external"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: Внешний ключ на пользователя (User.id)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    #: Маркетплейс (``"wb"`` или ``"ozon"``)
    marketplace: Mapped[str] = mapped_column(String(16), nullable=False)
    #: Схема доставки: ``"fbs"`` или ``"fbo"``
    scheme: Mapped[str] = mapped_column(String(8), nullable=False)
    #: Внешний идентификатор заказа/отправления (rid, posting_number и т.д.)
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    #: JSON‑представление оригинального ответа API
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    #: Дата создания события
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)