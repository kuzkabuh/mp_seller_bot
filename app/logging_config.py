"""
Версия файла: 1.1.0
Описание: Настройка логирования для приложения (stdout + опционально файл, ротация, единый формат, подавление шумных логгеров).
Дата изменения: 2025-12-28

Этот модуль содержит функцию `setup_logging`, которая конфигурирует
настройки логирования для всей программы. По умолчанию логи выводятся
в stdout (оптимально для Docker). Дополнительно доступна запись в файл
с ротацией и настройка уровней для "шумных" библиотек.

Поддерживаемые переменные окружения:
- LOG_LEVEL: уровень логирования (DEBUG/INFO/WARNING/ERROR/CRITICAL)
- LOG_TO_FILE: 1/true/yes/on — включить запись в файл
- LOG_FILE_PATH: путь к файлу логов (по умолчанию /var/log/mp_seller_bot/app.log)
- LOG_FILE_MAX_BYTES: размер файла до ротации (по умолчанию 10485760 = 10MB)
- LOG_FILE_BACKUP_COUNT: количество архивных файлов (по умолчанию 5)
- LOG_NOISY_LIBS_LEVEL: уровень для "шумных" логгеров (по умолчанию WARNING)

Примечание:
- Используется logging.basicConfig(..., force=True), чтобы избежать
  дублей логов при повторной инициализации в некоторых окружениях.
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
    """
    Преобразует строковые значения env в bool.
    """
    if val is None:
        return False
    return str(val).strip().lower() in ("1", "true", "yes", "y", "on")


def setup_logging(level: str = "INFO") -> None:
    """
    Настраивает базовую конфигурацию логирования.

    Args:
        level: Уровень логирования (например, "DEBUG", "INFO").
               Может быть переопределён переменной окружения LOG_LEVEL.
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
            # Если не можем создать файл/директорию (права, FS), не падаем — оставляем stdout.
            pass

    logging.basicConfig(
        level=root_level,
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
        force=True,
    )

    # Подавляем "шум" библиотек (можно переопределить через env)
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

1) config.py (или app/config.py) — где объявлен Settings/settings.
   Нужно синхронизировать имена параметров webhook и логирования с main.py,
   чтобы мы единообразно управляли режимом webhook/polling и уровнем логов.

2) Если config.py уже присылал ранее и он отличается от текущего — пришли именно тот,
   который реально лежит в репозитории и импортируется как `from config import settings`.

После этого я предложу минимальные правки в main.py (если нужно), чтобы он брал level из settings.
"""
