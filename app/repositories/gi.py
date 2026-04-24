from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GIRecord


class GIRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, rec: GIRecord) -> GIRecord:
        self.session.add(rec)
        await self.session.flush()
        return rec

    async def latest(self, user_id: int, limit: int = 10) -> list[GIRecord]:
        res = await self.session.execute(
            select(GIRecord)
            .where(GIRecord.user_id == user_id)
            .order_by(GIRecord.occurred_at.desc())
            .limit(limit)
        )
        return list(res.scalars())

    async def list_between(
        self, user_id: int, start: datetime, end: datetime
    ) -> list[GIRecord]:
        res = await self.session.execute(
            select(GIRecord)
            .where(
                and_(
                    GIRecord.user_id == user_id,
                    GIRecord.occurred_at >= start,
                    GIRecord.occurred_at < end,
                )
            )
            .order_by(GIRecord.occurred_at)
        )
        return list(res.scalars())
