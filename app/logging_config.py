"""
Версия файла: 1.0.0
Описание: Настройка логирования для приложения.
Дата изменения: 2025-12-27

Этот модуль содержит функцию `setup_logging`, которая конфигурирует
настройки логирования для всей программы. Логи выводятся в stdout с
форматом времени и уровнем, указанным в конфигурации.
"""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Настраивает базовую конфигурацию логирования.

    Args:
        level: Уровень логирования (например, "DEBUG", "INFO").
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="[%(asctime)s][%(levelname)s][%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )