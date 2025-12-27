# Версия файла: 1.0.0
# Описание: Настройки приложения (загрузка из .env / env)
# Дата изменения: 2025-12-27

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    database_url: str = Field(alias="DATABASE_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    timezone: str = Field(default="Europe/Moscow", alias="TIMEZONE")

    orders_poll_interval_seconds: int = Field(default=60, alias="ORDERS_POLL_INTERVAL_SECONDS")

    daily_summary_hour: int = Field(default=9, alias="DAILY_SUMMARY_HOUR")
    daily_summary_minute: int = Field(default=0, alias="DAILY_SUMMARY_MINUTE")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

