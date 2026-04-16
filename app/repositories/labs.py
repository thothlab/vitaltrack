from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LabResult


class LabRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, rec: LabResult) -> LabResult:
        self.session.add(rec)
        await self.session.flush()
        return rec

    async def latest(self, user_id: int) -> Optional[LabResult]:
        res = await self.session.execute(
            select(LabResult)
            .where(LabResult.user_id == user_id)
            .order_by(LabResult.drawn_at.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()

    async def list_between(
        self, user_id: int, start: datetime, end: datetime
    ) -> list[LabResult]:
        res = await self.session.execute(
            select(LabResult).where(
                LabResult.user_id == user_id,
                LabResult.drawn_at >= start,
                LabResult.drawn_at < end,
            ).order_by(LabResult.drawn_at)
        )
        return list(res.scalars())
