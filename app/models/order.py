# Версия файла: 1.0.0
# Описание: Заказы, полученные из маркетплейсов (для уведомлений/истории)
# Дата изменения: 2025-12-27

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("marketplace_account_id", "marketplace_order_id", name="uq_orders_account_order_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    marketplace_account_id: Mapped[int] = mapped_column(
        ForeignKey("marketplace_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    marketplace_order_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    warehouse: Mapped[str | None] = mapped_column(String(128), nullable=True)

    total_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)

    source_created_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Сырые данные ответа маркетплейса (для диагностики/расширения)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    marketplace_account: Mapped["MarketplaceAccount"] = relationship(back_populates="orders", lazy="selectin")


from app.models.marketplace_account import MarketplaceAccount  # noqa: E402
