# Версия файла: 1.1.0
# Описание: Модели БД (пользователи и аккаунты маркетплейсов с шифрованием API-ключей)
# Дата изменения: 2025-12-27

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MarketplaceAccount(Base):
    """
    Хранит подключение пользователя к WB/Ozon.
    Важно: api_key хранится зашифрованным (api_key_encrypted).
    """

    __tablename__ = "marketplace_accounts"
    __table_args__ = (
        UniqueConstraint("tg_user_id", "marketplace", name="uq_tg_user_marketplace"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)

    marketplace: Mapped[str] = mapped_column(String(16), nullable=False)  # "wb" | "ozon"
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
