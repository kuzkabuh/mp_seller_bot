# Версия файла: 1.0.0
# Описание: Перечисления (enums) для моделей БД
# Дата изменения: 2025-12-27

from __future__ import annotations

import enum


class MarketplaceType(str, enum.Enum):
    WB = "WB"
    OZON = "OZON"

