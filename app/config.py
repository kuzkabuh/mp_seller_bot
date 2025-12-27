# Версия файла: 1.1.0
# Описание: Централизованная конфигурация приложения (env -> настройки) + валидация
# Дата изменения: 2025-12-27

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Конфигурация бота. Все значения читаются из переменных окружения.
    В Docker Compose они пробрасываются из .env файла.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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

    # Scheduler
    poll_interval_seconds: int = Field(60, alias="POLL_INTERVAL_SECONDS")

    # Logging
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    def database_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
