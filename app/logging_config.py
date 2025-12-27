# Версия файла: 1.1.0
# Описание: Настройка логирования (единый формат, уровни, безопасный вывод)
# Дата изменения: 2025-12-27

from __future__ import annotations

import logging
import os
import sys


def setup_logging(level: str = "INFO") -> None:
    lvl = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(lvl)

    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="[%(asctime)s][%(levelname)s][%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Чуть уменьшаем шум библиотек
    logging.getLogger("aiogram").setLevel(max(lvl, logging.INFO))
    logging.getLogger("sqlalchemy.engine").setLevel(max(lvl, logging.WARNING))

    # На всякий случай: отключаем буферизацию stdout в контейнере
    os.environ["PYTHONUNBUFFERED"] = "1"
