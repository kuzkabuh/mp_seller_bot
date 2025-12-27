"""
Версия файла: 1.3.0
Описание: Конфигурация приложения и чтение переменных окружения (pydantic-settings) с валидацией и совместимостью.
Дата изменения: 2025-12-28

Модуль определяет класс Settings, который считывает параметры из
переменных окружения и/или файла .env (используется pydantic-settings).
Конфигурация охватывает токен Telegram-бота, Fernet-ключ для шифрования
данных, параметры подключения к базе данных, настройки вебхука, логирования
и сервисные флаги.

Ключевые улучшения:
- Совместимость с несколькими названиями переменных (BOT_TOKEN/TELEGRAM_BOT_TOKEN,
  WEBHOOK_BASE_URL/BASE_WEBHOOK_URL, WEBHOOK_LISTEN_HOST/WEBHOOK_HOST и т.д.).
- Нормализация значений (обрезка пробелов, удаление хвостовых слешей).
- Валидация критических параметров (FERNET_KEY, WEBHOOK_SECRET длина, порт).
- Удобные computed-свойства и методы: database_dsn(), webhook_enabled,
  webhook_url(), webhook_path_effective, webhook_listen_host_effective и др.
- Сохранена обратная совместимость с ранее использованными именами полей.
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Класс конфигурации для приложения.

    Читает значения из `.env` или переменных окружения. Использование pydantic
    облегчает валидацию и создание типизированных параметров.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ----------------------------
    # Telegram
    # ----------------------------
    # Основной токен. Дополнительно поддерживаем TELEGRAM_BOT_TOKEN через валидатор.
    bot_token: str = Field(..., alias="BOT_TOKEN")

    # ----------------------------
    # Crypto
    # ----------------------------
    fernet_key: str = Field(..., alias="FERNET_KEY")

    # ----------------------------
    # Postgres
    # ----------------------------
    postgres_host: str = Field("db", alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")
    postgres_db: str = Field("mp_seller_bot", alias="POSTGRES_DB")
    postgres_user: str = Field("mpbot", alias="POSTGRES_USER")
    postgres_password: str = Field(..., alias="POSTGRES_PASSWORD")

    # ----------------------------
    # Scheduler / Polling
    # ----------------------------
    poll_interval_seconds: int = Field(60, alias="POLL_INTERVAL_SECONDS")

    # ----------------------------
    # Logging
    # ----------------------------
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    # ----------------------------
    # Webhook settings (совместимость + новые имена)
    # ----------------------------
    # USE_WEBHOOK: явный флаг. Также поддерживаем WEBHOOK_ENABLED в валидаторе.
    use_webhook: bool = Field(False, alias="USE_WEBHOOK")

    # Где слушает aiohttp внутри контейнера
    webhook_host: Optional[str] = Field(None, alias="WEBHOOK_HOST")
    webhook_port: int = Field(8000, alias="WEBHOOK_PORT")

    # Явный путь, если хотите фиксированный. Если не задан — берём "/webhook".
    # Если задан WEBHOOK_SECRET, в приложении рекомендуется путь "/webhook/<secret>".
    webhook_path: str = Field("/webhook", alias="WEBHOOK_PATH")

    # Внешний URL домена, например: https://mpsellerbot.kuzkabuh.ru
    # Поддерживаем оба варианта: BASE_WEBHOOK_URL (старый) и WEBHOOK_BASE_URL (новый) через валидатор.
    base_webhook_url: Optional[str] = Field(None, alias="BASE_WEBHOOK_URL")

    # Секрет для формирования пути /webhook/<secret> и/или проверки входящих запросов.
    webhook_secret: Optional[str] = Field(None, alias="WEBHOOK_SECRET")

    # Дополнительные параметры для совместимости с main.py (если есть)
    # WEBHOOK_LISTEN_HOST / WEBHOOK_LISTEN_PORT / WEBHOOK_BASE_URL / WEBHOOK_ENABLED
    # Эти поля необязательны: читаем из окружения через aliases-валидаторы ниже.
    webhook_listen_host: Optional[str] = Field(None, alias="WEBHOOK_LISTEN_HOST")
    webhook_listen_port: Optional[int] = Field(None, alias="WEBHOOK_LISTEN_PORT")
    webhook_base_url: Optional[str] = Field(None, alias="WEBHOOK_BASE_URL")
    webhook_enabled_flag: Optional[str] = Field(None, alias="WEBHOOK_ENABLED")

    # ----------------------------
    # Validators / Normalizers
    # ----------------------------
    @field_validator("bot_token", mode="before")
    @classmethod
    def _bot_token_from_alt_env(cls, v):
        """
        Поддержка альтернативной переменной TELEGRAM_BOT_TOKEN, если BOT_TOKEN не задан.
        Pydantic передаст None/'' если отсутствует. В таком случае пытаемся взять из окружения.
        """
        if v is None or (isinstance(v, str) and not v.strip()):
            import os

            alt = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
            if alt:
                return alt
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("fernet_key", mode="before")
    @classmethod
    def _strip_fernet_key(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, v):
        if isinstance(v, str):
            return v.strip().upper()
        return v

    @field_validator("postgres_host", "postgres_db", "postgres_user", mode="before")
    @classmethod
    def _strip_postgres_strings(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("postgres_port", mode="before")
    @classmethod
    def _coerce_postgres_port(cls, v):
        try:
            return int(str(v).strip())
        except Exception:
            return 5432

    @field_validator("poll_interval_seconds", mode="before")
    @classmethod
    def _coerce_poll_interval(cls, v):
        try:
            vv = int(str(v).strip())
        except Exception:
            vv = 60
        if vv < 5:
            vv = 5
        return vv

    @field_validator("webhook_port", mode="before")
    @classmethod
    def _coerce_webhook_port(cls, v):
        try:
            vv = int(str(v).strip())
        except Exception:
            vv = 8000
        if vv < 1 or vv > 65535:
            vv = 8000
        return vv

    @field_validator("webhook_listen_port", mode="before")
    @classmethod
    def _coerce_webhook_listen_port(cls, v):
        if v is None:
            return None
        try:
            vv = int(str(v).strip())
        except Exception:
            return None
        if vv < 1 or vv > 65535:
            return None
        return vv

    @field_validator("webhook_host", "webhook_listen_host", mode="before")
    @classmethod
    def _strip_webhook_hosts(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            vv = v.strip()
            return vv if vv else None
        return v

    @field_validator("webhook_path", mode="before")
    @classmethod
    def _normalize_webhook_path(cls, v):
        if not isinstance(v, str):
            return "/webhook"
        vv = v.strip()
        if not vv:
            return "/webhook"
        if not vv.startswith("/"):
            vv = "/" + vv
        if vv != "/" and vv.endswith("/"):
            vv = vv.rstrip("/")
        return vv

    @field_validator("base_webhook_url", mode="before")
    @classmethod
    def _base_webhook_url_support_alt_names(cls, v):
        """
        BASE_WEBHOOK_URL (старый) или WEBHOOK_BASE_URL (новый).
        Если base_webhook_url не задан — попробуем взять WEBHOOK_BASE_URL из окружения.
        """
        import os

        if v is None or (isinstance(v, str) and not v.strip()):
            alt = os.getenv("WEBHOOK_BASE_URL") or os.getenv("BASE_WEBHOOK_URL")
            if alt:
                v = alt
        if isinstance(v, str):
            vv = v.strip().rstrip("/")
            return vv if vv else None
        return v

    @field_validator("webhook_base_url", mode="before")
    @classmethod
    def _webhook_base_url_strip(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            vv = v.strip().rstrip("/")
            return vv if vv else None
        return v

    @field_validator("webhook_secret", mode="before")
    @classmethod
    def _strip_webhook_secret(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            vv = v.strip()
            return vv if vv else None
        return v

    @field_validator("use_webhook", mode="before")
    @classmethod
    def _use_webhook_support_alt_flag(cls, v):
        """
        Поддерживаем:
        - USE_WEBHOOK (основной)
        - WEBHOOK_ENABLED (альтернатива из main.py)
        - Автовключение при наличии WEBHOOK_BASE_URL/BASE_WEBHOOK_URL (можно использовать ниже в webhook_enabled property)
        """
        def _to_bool(x: object) -> bool:
            if x is None:
                return False
            s = str(x).strip().lower()
            return s in ("1", "true", "yes", "y", "on")

        if isinstance(v, bool):
            return v

        # если USE_WEBHOOK не задан — попробуем WEBHOOK_ENABLED
        if v is None or (isinstance(v, str) and not v.strip()):
            import os

            alt = os.getenv("WEBHOOK_ENABLED")
            if alt is not None and str(alt).strip() != "":
                return _to_bool(alt)
            return False

        return _to_bool(v)

    # ----------------------------
    # Public helpers / properties
    # ----------------------------
    def database_dsn(self) -> str:
        """Возвращает DSN строку подключения к базе данных (asyncpg)."""
        user = (self.postgres_user or "").strip()
        pwd = (self.postgres_password or "").strip()
        host = (self.postgres_host or "").strip()
        dbn = (self.postgres_db or "").strip()
        port = int(self.postgres_port)
        return f"postgresql+asyncpg://{user}:{pwd}@{host}:{port}/{dbn}"

    @property
    def webhook_base_url_effective(self) -> Optional[str]:
        """
        Итоговый base url для установки webhook в Telegram.
        Приоритет:
        1) WEBHOOK_BASE_URL (если задан отдельным полем)
        2) BASE_WEBHOOK_URL (старое имя)
        """
        if self.webhook_base_url:
            return self.webhook_base_url.strip().rstrip("/")
        if self.base_webhook_url:
            return self.base_webhook_url.strip().rstrip("/")
        return None

    @property
    def webhook_listen_host_effective(self) -> str:
        """
        Итоговый хост, на котором слушает aiohttp внутри контейнера.
        Приоритет:
        1) WEBHOOK_LISTEN_HOST
        2) WEBHOOK_HOST
        3) 0.0.0.0
        """
        if self.webhook_listen_host:
            return self.webhook_listen_host.strip()
        if self.webhook_host:
            return self.webhook_host.strip()
        return "0.0.0.0"

    @property
    def webhook_listen_port_effective(self) -> int:
        """
        Итоговый порт, на котором слушает aiohttp внутри контейнера.
        Приоритет:
        1) WEBHOOK_LISTEN_PORT
        2) WEBHOOK_PORT
        3) 8000
        """
        if self.webhook_listen_port is not None:
            try:
                vv = int(self.webhook_listen_port)
                if 1 <= vv <= 65535:
                    return vv
            except Exception:
                pass
        try:
            vv2 = int(self.webhook_port)
            if 1 <= vv2 <= 65535:
                return vv2
        except Exception:
            pass
        return 8000

    @property
    def webhook_path_effective(self) -> str:
        """
        Итоговый путь webhook:
        - Если задан webhook_secret → /webhook/<secret>
        - Иначе → webhook_path (по умолчанию /webhook)
        """
        base_path = self.webhook_path or "/webhook"
        if not base_path.startswith("/"):
            base_path = "/" + base_path
        base_path = base_path.rstrip("/") if base_path != "/" else base_path
        if self.webhook_secret:
            return f"{base_path}/{self.webhook_secret}"
        return base_path

    @property
    def webhook_enabled(self) -> bool:
        """
        Итоговое решение: запускать webhook или polling.

        Логика:
        - Если use_webhook=True → webhook
        - Или если задан webhook_base_url_effective → webhook
        - Иначе polling
        """
        if bool(self.use_webhook):
            return True
        return bool(self.webhook_base_url_effective)

    def webhook_url(self) -> Optional[str]:
        """
        Возвращает полный URL webhook для Telegram (base + path),
        либо None если base url не задан.
        """
        base = self.webhook_base_url_effective
        if not base:
            return None
        return f"{base}{self.webhook_path_effective}"

    def validate_runtime(self) -> None:
        """
        Дополнительная валидация, которую можно вызывать на старте приложения.
        Не является обязательной для pydantic, но помогает выдавать понятные ошибки.
        """
        if not self.bot_token or not self.bot_token.strip():
            raise ValueError("BOT_TOKEN не задан. Укажите BOT_TOKEN или TELEGRAM_BOT_TOKEN.")

        if not self.fernet_key or not self.fernet_key.strip():
            raise ValueError("FERNET_KEY не задан. Укажите FERNET_KEY в .env.")

        # Если включен webhook — проверим базовые требования.
        if self.webhook_enabled:
            base = self.webhook_base_url_effective
            if not base:
                raise ValueError(
                    "Webhook включен, но не задан WEBHOOK_BASE_URL/BASE_WEBHOOK_URL. "
                    "Укажите, например: https://mpsellerbot.kuzkabuh.ru"
                )

            # Секрет настоятельно рекомендуется
            if not self.webhook_secret:
                # Не падаем, но предупреждаем через исключение нельзя. Пусть вызывающий логирует.
                return

            if len(self.webhook_secret) < 32:
                raise ValueError("WEBHOOK_SECRET слишком короткий. Рекомендуется 32+ символа.")


settings = Settings()
