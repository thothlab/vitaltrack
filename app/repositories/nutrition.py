from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MealRecord


class NutritionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, rec: MealRecord) -> MealRecord:
        self.session.add(rec)
        await self.session.flush()
        return rec

    async def list_between(
        self, user_id: int, start: datetime, end: datetime
    ) -> list[MealRecord]:
        res = await self.session.execute(
            select(MealRecord)
            .where(
                MealRecord.user_id == user_id,
                MealRecord.eaten_at >= start,
                MealRecord.eaten_at < end,
            )
            .order_by(MealRecord.eaten_at)
        )
        return list(res.scalars())
