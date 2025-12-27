# Версия файла: 1.0.0
# Описание: Товар (SKU) маркетплейса, связанный с аккаунтом продавца
# Дата изменения: 2025-12-27

from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Product(Base, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("marketplace_account_id", "external_sku", name="uq_products_account_sku"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    marketplace_account_id: Mapped[int] = mapped_column(
        ForeignKey("marketplace_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    # nmId / offer_id / product_id — зависит от МП, храним как строку
    external_sku: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    marketplace_account: Mapped["MarketplaceAccount"] = relationship(back_populates="products", lazy="selectin")
    stocks: Mapped[list["Stock"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


from app.models.marketplace_account import MarketplaceAccount  # noqa: E402
from app.models.stock import Stock  # noqa: E402
