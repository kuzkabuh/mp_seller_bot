# Версия файла: 1.0.0
# Описание: Остатки товара на складе маркетплейса
# Дата изменения: 2025-12-27

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Stock(Base, TimestampMixin):
    __tablename__ = "stocks"
    __table_args__ = (UniqueConstraint("product_id", "warehouse_name", name="uq_stocks_product_warehouse"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)

    warehouse_name: Mapped[str] = mapped_column(String(256), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    product: Mapped["Product"] = relationship(back_populates="stocks", lazy="selectin")


from app.models.product import Product  # noqa: E402
