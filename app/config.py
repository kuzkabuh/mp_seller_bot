"""
Версия файла: 1.2.0
Описание: Конфигурация приложения и чтение переменных окружения.
Дата изменения: 2025-12-27

Модуль определяет класс Settings, который считывает параметры из
переменных окружения (используется pydantic-settings). Конфигурация
охватывает токен Telegram‑бота, Fernet‑ключ для шифрования данных,
параметры подключения к базе данных, настройки вебхука и логирования.

Новые параметры для вебхука позволяют переключаться между режимами
поллинга и webhook. Если USE_WEBHOOK=true, бот будет запускать
aiohttp‑приложение, привязанное к указанному хосту и порту и
регистрационный путь WEBHOOK_PATH. BASE_WEBHOOK_URL используется для
установки URL вебхука в Telegram. WEBHOOK_SECRET задаёт секретный токен
для проверки входящих запросов.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Класс конфигурации для приложения.

    Читает значения из `.env` или переменных окружения. Использование
    pydantic облегчает валидацию и создание типа данных.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Telegram
    bot_token: str = Field(..., alias="BOT_TOKEN")

    # Crypto
    fernet_key: str = Field(..., alias="FERNET_KEY")

    # Postgres
    postgres_host: str = Field("db", alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")
    postgres_db: str = Field("mp_seller_bot", alias="POSTGRES_DB")
    postgres_user: str = Field("mpbot", alias="POSTGRES_USER")
    postgres_password: str = Field(..., alias="POSTGRES_PASSWORD")

    # Scheduler / Polling
    poll_interval_seconds: int = Field(60, alias="POLL_INTERVAL_SECONDS")

    # Logging
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    # Webhook settings
    use_webhook: bool = Field(False, alias="USE_WEBHOOK")
    webhook_host: str | None = Field(None, alias="WEBHOOK_HOST")
    webhook_port: int = Field(8000, alias="WEBHOOK_PORT")
    webhook_path: str = Field("/webhook", alias="WEBHOOK_PATH")
    base_webhook_url: str | None = Field(None, alias="BASE_WEBHOOK_URL")
    webhook_secret: str | None = Field(None, alias="WEBHOOK_SECRET")

    def database_dsn(self) -> str:
        """Возвращает DSN строки подключения к базе данных."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()