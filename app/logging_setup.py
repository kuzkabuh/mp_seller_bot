"""
Версия файла: 1.1.0
Описание: Настройка логирования для mp_seller_bot (консоль + опционально файл, единый формат, подавление шумных логгеров)
Дата изменения: 2025-12-28

Изменения:
- Добавлен безопасный парсинг уровня логирования.
- Добавлена поддержка вывода в файл (LOG_TO_FILE=1 и LOG_FILE_PATH).
- Добавлена ротация логов (LOG_FILE_MAX_BYTES, LOG_FILE_BACKUP_COUNT).
- Добавлено единое форматирование, вывод в stdout по умолчанию (под Docker).
- Снижена "шумность" некоторых библиотек (aiohttp, aiogram) через настройку уровней.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional


def _normalize_level(level: Optional[str]) -> int:
    """
    Нормализует строковый уровень логирования в logging-константу.
    """
    if not level:
        return logging.INFO
    name = str(level).strip().upper()
    return getattr(logging, name, logging.INFO)


def _bool_env(val: Optional[str]) -> bool:
    if val is None:
        return False
    return str(val).strip().lower() in ("1", "true", "yes", "y", "on")


def setup_logging(level: str = "INFO") -> None:
    """
    Настраивает логирование приложения.

    По умолчанию:
    - вывод в stdout (удобно для Docker)
    - формат: [YYYY-mm-dd HH:MM:SS][LEVEL][logger] message

    Дополнительно через env:
    - LOG_LEVEL: переопределяет level
    - LOG_TO_FILE=1: включает запись в файл
    - LOG_FILE_PATH: путь к файлу логов (по умолчанию /var/log/mp_seller_bot/app.log)
    - LOG_FILE_MAX_BYTES: максимальный размер файла до ротации (по умолчанию 10MB)
    - LOG_FILE_BACKUP_COUNT: сколько архивных файлов хранить (по умолчанию 5)
    - LOG_NOISY_LIBS_LEVEL: уровень для "шумных" логгеров (по умолчанию WARNING)
    """
    env_level = os.getenv("LOG_LEVEL")
    effective_level = env_level if env_level is not None and str(env_level).strip() else level
    root_level = _normalize_level(effective_level)

    fmt = "[%(asctime)s][%(levelname)s][%(name)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if _bool_env(os.getenv("LOG_TO_FILE")):
        log_path = os.getenv("LOG_FILE_PATH") or "/var/log/mp_seller_bot/app.log"
        max_bytes_raw = os.getenv("LOG_FILE_MAX_BYTES") or "10485760"  # 10MB
        backup_count_raw = os.getenv("LOG_FILE_BACKUP_COUNT") or "5"

        try:
            max_bytes = int(str(max_bytes_raw).strip())
        except Exception:
            max_bytes = 10485760

        try:
            backup_count = int(str(backup_count_raw).strip())
        except Exception:
            backup_count = 5

        # На случай, если директория не существует или нет прав — не падаем.
        try:
            os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            handlers.append(file_handler)
        except Exception:
            # Если нельзя писать в файл, оставляем только stdout
            pass

    logging.basicConfig(
        level=root_level,
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
        force=True,  # важно: переинициализируем конфиг, чтобы в Docker/uvicorn не было дублей
    )

    # Подавляем "шум" библиотек по умолчанию, но оставляем возможность переопределить.
    noisy_level_name = os.getenv("LOG_NOISY_LIBS_LEVEL") or "WARNING"
    noisy_level = _normalize_level(noisy_level_name)

    for logger_name in (
        "aiohttp.access",
        "aiohttp.client",
        "aiogram.event",
        "aiogram.dispatcher",
        "aiogram.middlewares",
        "asyncio",
    ):
        logging.getLogger(logger_name).setLevel(noisy_level)


"""
Какой файл прислать следующим:

Чтобы логирование было единым и управляемым из .env, лучше синхронизировать вызов setup_logging() в главном файле.
Пришли, пожалуйста, следующий файл для правки:

- config.py (или где у тебя находится Settings/settings и импортируется `settings`)

Причина: мы можем передавать settings.log_level в setup_logging(settings.log_level),
а также централизованно задать переменные LOG_TO_FILE/LOG_FILE_PATH в конфиге.
"""
