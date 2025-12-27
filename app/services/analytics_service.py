"""
Версия файла: 1.0.0
Описание: Сервис аналитики (черновик) для mp_seller_bot
Дата изменения: 2025-12-27
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AnalyticsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def orders_count_last_days(self, user_id: int, days: int = 7) -> dict[str, int]:
        sql = text(
            """
            SELECT marketplace, scheme, COUNT(*) AS cnt
            FROM order_events
            WHERE user_id = :user_id
              AND created_at >= (NOW() - (:days || ' days')::interval)
            GROUP BY marketplace, scheme
            """
        )
        res = await self.session.execute(sql, {"user_id": user_id, "days": days})
        rows = res.fetchall()

        out: dict[str, int] = {}
        for marketplace, scheme, cnt in rows:
            out[f"{marketplace}:{scheme}"] = int(cnt)
        return out

    async def revenue_tips_stub(self) -> list[str]:
        """
        Заготовка: в будущем здесь будут подсказки по выручке на основе данных:
        - конверсия заказ->выкуп
        - потеря выручки из-за OOS
        - цены относительно конкурентов
        - доля рекламных затрат и т.д.
        """
        return [
            "Проверьте наличие на складе по топ-SKU за последние 7 дней: частая причина просадки — out-of-stock.",
            "Сфокусируйтесь на 20% SKU, которые дают 80% заказов: улучшайте карточки и остатки в первую очередь.",
            "Если заказы есть, но выручка не растет — вероятно падает средний чек: проверьте цену и комплекты.",
        ]

