"""
Версия файла: 1.0.0
Описание: Детектор новых заказов/постингов и дедупликация для mp_seller_bot
Дата изменения: 2025-12-27

В этом модуле определены утилиты для выбора уникального внешнего
идентификатора заказа из произвольного словаря и сериализации
payload. Они используются воркером notifier при обработке новых
событий.
"""

from __future__ import annotations

import json
from typing import Iterable


def safe_external_id(item: dict, fallback_fields: Iterable[str]) -> str:
    """
    Возвращает первый непустой идентификатор из указанных полей. Если
    подходящее поле не найдено, возвращает укороченный JSON объекта.
    """
    for f in fallback_fields:
        val = item.get(f)
        if val is not None and str(val).strip() != "":
            return str(val)
    return json.dumps(item, ensure_ascii=False)[:120]


def to_json(item: dict) -> str:
    """Сериализует словарь в JSON (UTF-8)."""
    return json.dumps(item, ensure_ascii=False)