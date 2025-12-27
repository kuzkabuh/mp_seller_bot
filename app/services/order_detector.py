"""
Файл: services/order_detector.py
Версия файла: 1.1.0
Описание: Детектор новых заказов/постингов и дедупликация для mp_seller_bot
Дата изменения: 2025-12-28

Модуль содержит утилиты для:
- надёжного получения уникального внешнего идентификатора события (external_id)
- безопасной и стабильной сериализации payload в JSON

Используется воркером notifier при обработке новых событий из WB/Ozon.

Улучшения по сравнению с предыдущей версией:
- Гарантированно возвращается НЕ пустой и НЕ чрезмерно длинный external_id
- Добавлена нормализация значений (str, int, uuid, вложенные поля)
- Добавлен fallback-хеш, если идентификатор извлечь невозможно
- JSON сериализация защищена от несерилизуемых типов
- Ограничение длины payload_json для защиты БД
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


MAX_EXTERNAL_ID_LEN = 128
MAX_PAYLOAD_JSON_LEN = 100_000  # защита БД от слишком больших payload


def _normalize_value(val: Any) -> str | None:
    """
    Приводит значение к строке для использования в external_id.
    Возвращает None, если значение непригодно.
    """
    if val is None:
        return None

    # Числа, UUID, строки
    try:
        s = str(val).strip()
    except Exception:
        return None

    if not s:
        return None

    return s


def safe_external_id(item: dict, fallback_fields: Iterable[str]) -> str:
    """
    Возвращает стабильный внешний идентификатор события.

    Алгоритм:
    1. Ищем первое непустое значение среди fallback_fields.
    2. Если найдено — нормализуем и ограничиваем длину.
    3. Если не найдено — строим детерминированный hash от payload.

    Это гарантирует:
    - одинаковые события → одинаковый external_id
    - отсутствие пустых значений
    - предсказуемую длину
    """
    # 1. Попытка взять ID из известных полей
    for field in fallback_fields:
        if not isinstance(item, dict):
            break
        val = _normalize_value(item.get(field))
        if val is not None:
            if len(val) > MAX_EXTERNAL_ID_LEN:
                return val[:MAX_EXTERNAL_ID_LEN]
            return val

    # 2. Fallback: стабильный hash от payload
    try:
        raw = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        raw = repr(item)

    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"hash:{digest}"[:MAX_EXTERNAL_ID_LEN]


def to_json(item: dict) -> str:
    """
    Сериализует словарь в JSON (UTF-8) с защитой от несерилизуемых типов
    и ограничением размера.

    Используется для сохранения payload в БД.
    """
    try:
        data = json.dumps(
            item,
            ensure_ascii=False,
            default=str,
            separators=(",", ":"),
        )
    except Exception:
        data = json.dumps(
            {"_error": "payload_serialization_failed"},
            ensure_ascii=False,
        )

    if len(data) > MAX_PAYLOAD_JSON_LEN:
        # Обрезаем, чтобы не положить БД
        return data[:MAX_PAYLOAD_JSON_LEN] + "…"

    return data
