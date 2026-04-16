from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SymptomRecord


class SymptomRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, rec: SymptomRecord) -> SymptomRecord:
        self.session.add(rec)
        await self.session.flush()
        return rec

    async def list_between(
        self, user_id: int, start: datetime, end: datetime
    ) -> list[SymptomRecord]:
        res = await self.session.execute(
            select(SymptomRecord)
            .where(
                SymptomRecord.user_id == user_id,
                SymptomRecord.occurred_at >= start,
                SymptomRecord.occurred_at < end,
            )
            .order_by(SymptomRecord.occurred_at)
        )
        return list(res.scalars())
