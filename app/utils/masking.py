# Версия файла: 1.0.0
# Описание: Маскирование чувствительных данных (токены, ключи)
# Дата изменения: 2025-12-27

from __future__ import annotations


def mask_secret(value: str | None, left: int = 4, right: int = 4) -> str:
    if not value:
        return ""
    s = value.strip()
    if len(s) <= left + right + 3:
        return "*" * len(s)
    return f"{s[:left]}...{s[-right:]}"

