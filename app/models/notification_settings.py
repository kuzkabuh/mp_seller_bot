# Версия файла: 1.0.0
# Описание: Настройки уведомлений для подключенного маркетплейса
# Дата изменения: 2025-12-27

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class NotificationSettings(Base, TimestampMixin):
    __tablename__ = "notification_settings"
    __table_args__ = (
        UniqueConstraint("marketplace_account_id", name="uq_notification_settings_marketplace_account_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    marketplace_account_id: Mapped[int] = mapped_column(
        ForeignKey("marketplace_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    notify_new_orders: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    daily_summary_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    low_stock_alert_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    marketplace_account: Mapped["MarketplaceAccount"] = relationship(back_populates="notification_settings", lazy="selectin")


from app.models.marketplace_account import MarketplaceAccount  # noqa: E402
