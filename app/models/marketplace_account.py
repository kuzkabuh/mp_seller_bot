# Версия файла: 1.0.0
# Описание: Модель подключения аккаунта маркетплейса (WB/Ozon) к пользователю
# Дата изменения: 2025-12-27

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import MarketplaceType


class MarketplaceAccount(Base, TimestampMixin):
    __tablename__ = "marketplace_accounts"
    __table_args__ = (UniqueConstraint("user_id", "marketplace_type", name="uq_marketplace_accounts_user_mp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    marketplace_type: Mapped[MarketplaceType] = mapped_column(
        Enum(MarketplaceType, name="marketplace_type"),
        nullable=False,
    )

    # ВАЖНО: API-ключ WB может быть ~500+ символов => TEXT без усечения
    api_key: Mapped[str] = mapped_column(Text, nullable=False)

    # Для Ozon обычно требуется client_id
    client_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    last_orders_check_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_order_marker: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="marketplace_accounts", lazy="selectin")

    notification_settings: Mapped["NotificationSettings"] = relationship(
        back_populates="marketplace_account",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )

    orders: Mapped[list["Order"]] = relationship(
        back_populates="marketplace_account",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    products: Mapped[list["Product"]] = relationship(
        back_populates="marketplace_account",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


from app.models.notification_settings import NotificationSettings  # noqa: E402
from app.models.order import Order  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.user import User  # noqa: E402
