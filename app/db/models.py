# Версия файла: 2.1.0
# Описание: ORM-модели для mp_seller_bot (связи, индексы, ограничения, подготовка к расширению аналитики/уведомлений).
# Дата изменения: 2025-12-28
#
# Изменения:
# - Добавлены внешние ключи и связи relationship (User ↔ MarketplaceCredential, User ↔ OrderEvent).
# - Добавлены индексы для типовых запросов репозитория/воркера (активные креды, поиск событий).
# - Усилена семантика полей marketplace/scheme (ограничения CheckConstraint).
# - Добавлены updated_at для users (на будущее: обновление профиля, last_seen).
# - Добавлены поля user_id FK в credential/events с ondelete="CASCADE" (без "висячих" записей).
# - Уточнены типы и длины строк, выровнены server_default/onupdate.
# - Подготовлены "расширяемые" поля для будущих функций (например, last_error, last_checked_at) — НЕ добавлены,
#   чтобы не ломать существующую схему без миграций. Оставлены как комментарии.

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    #: Дата обновления (например, username). Полезно для аудита.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Связи (relationship) — удобны для админки/аналитики/отладки
    credentials: Mapped[list["MarketplaceCredential"]] = relationship(
        "MarketplaceCredential",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    order_events: Mapped[list["OrderEvent"]] = relationship(
        "OrderEvent",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class MarketplaceCredential(Base):
    """
    Учётные данные для подключения к маркетплейсам.

    Для Wildberries требуется только API ключ, поэтому поле
    encrypted_client_id будет NULL. Для Ozon нужны client_id и api_key.
    В целях безопасности оба значения сохраняются в зашифрованном виде.

    Поле tg_user_id дублирует Telegram-ID для быстрого отправления
    уведомлений без дополнительных запросов.
    """

    __tablename__ = "marketplace_credentials"
    __table_args__ = (
        UniqueConstraint("user_id", "marketplace", name="uq_user_marketplace"),
        CheckConstraint("marketplace IN ('wb','ozon')", name="ck_marketplace_credentials_marketplace"),
        Index("ix_marketplace_credentials_user_marketplace", "user_id", "marketplace"),
        Index("ix_marketplace_credentials_user_active", "user_id", "is_active"),
        Index("ix_marketplace_credentials_marketplace_active", "marketplace", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: Внешний ключ на пользователя (User.id)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    #: Telegram ID пользователя для отправки сообщений
    tg_user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)

    #: Код маркетплейса: "wb" или "ozon"
    marketplace: Mapped[str] = mapped_column(String(16), nullable=False)

    #: Зашифрованный API ключ
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)

    #: Зашифрованный client_id (для Ozon), NULL для WB
    encrypted_client_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Флаг активности. Деактивация позволяет временно отключить мониторинг
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    #: Дата создания записи
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    #: Дата последнего обновления записи
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Примеры будущих полей (пока не добавляем без миграций):
    # last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="credentials", lazy="selectin")


class OrderEvent(Base):
    """
    Событие заказа. Каждая запись соответствует одному поступлению заказа/отправления.
    Используется для дедупликации уведомлений – если комбинация
    user_id, marketplace, scheme и external_id уже существует, бот не отправляет
    повторное уведомление.
    """

    __tablename__ = "order_events"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "marketplace",
            "scheme",
            "external_id",
            name="uq_user_marketplace_scheme_external",
        ),
        CheckConstraint("marketplace IN ('wb','ozon')", name="ck_order_events_marketplace"),
        CheckConstraint("scheme IN ('fbs','fbo')", name="ck_order_events_scheme"),
        Index("ix_order_events_user_created_at", "user_id", "created_at"),
        Index("ix_order_events_marketplace_scheme_created_at", "marketplace", "scheme", "created_at"),
        Index("ix_order_events_user_marketplace_scheme_external", "user_id", "marketplace", "scheme", "external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: Внешний ключ на пользователя (User.id)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    #: Маркетплейс ("wb" или "ozon")
    marketplace: Mapped[str] = mapped_column(String(16), nullable=False)

    #: Схема доставки: "fbs" или "fbo"
    scheme: Mapped[str] = mapped_column(String(8), nullable=False)

    #: Внешний идентификатор заказа/отправления (rid, posting_number и т.д.)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)

    #: JSON-представление оригинального ответа API
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)

    #: Дата создания события
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="order_events", lazy="selectin")
