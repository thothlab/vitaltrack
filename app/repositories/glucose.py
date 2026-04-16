from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GlucoseRecord


class GlucoseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, record: GlucoseRecord) -> GlucoseRecord:
        self.session.add(record)
        await self.session.flush()
        return record

    async def list_between(
        self, user_id: int, start: datetime, end: datetime
    ) -> list[GlucoseRecord]:
        res = await self.session.execute(
            select(GlucoseRecord)
            .where(
                GlucoseRecord.user_id == user_id,
                GlucoseRecord.measured_at >= start,
                GlucoseRecord.measured_at < end,
            )
            .order_by(GlucoseRecord.measured_at)
        )
        return list(res.scalars())

    async def latest(self, user_id: int, limit: int = 5) -> list[GlucoseRecord]:
        res = await self.session.execute(
            select(GlucoseRecord)
            .where(GlucoseRecord.user_id == user_id)
            .order_by(GlucoseRecord.measured_at.desc())
            .limit(limit)
        )
        return list(res.scalars())

    async def latest_one(self, user_id: int) -> Optional[GlucoseRecord]:
        rows = await self.latest(user_id, 1)
        return rows[0] if rows else None
