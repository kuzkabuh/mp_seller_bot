"""
Версия файла: 1.0.0
Описание: ORM-модели БД для mp_seller_bot
Дата изменения: 2025-12-27
"""

from __future__ import annotations

import datetime as dt
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    tg_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=False), default=lambda: dt.datetime.utcnow())

    credentials: Mapped[list["MarketplaceCredential"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class MarketplaceCredential(Base):
    __tablename__ = "marketplace_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    marketplace: Mapped[str] = mapped_column(String(32), nullable=False)  # wb | ozon
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)  # WB key may be ~500+ chars

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=False), default=lambda: dt.datetime.utcnow())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=False), default=lambda: dt.datetime.utcnow())

    user: Mapped["User"] = relationship(back_populates="credentials")

    __table_args__ = (
        Index("ix_credentials_user_marketplace", "user_id", "marketplace", unique=True),
    )


class OrderEvent(Base):
    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    marketplace: Mapped[str] = mapped_column(String(32), nullable=False)  # wb | ozon
    scheme: Mapped[str] = mapped_column(String(16), nullable=False)       # fbs | fbo

    external_id: Mapped[str] = mapped_column(String(128), nullable=False) # posting_id/order_id
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=False), default=lambda: dt.datetime.utcnow())

    __table_args__ = (
        Index("ix_order_events_dedup", "user_id", "marketplace", "scheme", "external_id", unique=True),
    )
