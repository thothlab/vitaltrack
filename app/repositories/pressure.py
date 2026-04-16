from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PressureRecord


class PressureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, record: PressureRecord) -> PressureRecord:
        self.session.add(record)
        await self.session.flush()
        return record

    async def list_between(
        self, user_id: int, start: datetime, end: datetime
    ) -> list[PressureRecord]:
        res = await self.session.execute(
            select(PressureRecord)
            .where(
                PressureRecord.user_id == user_id,
                PressureRecord.measured_at >= start,
                PressureRecord.measured_at < end,
            )
            .order_by(PressureRecord.measured_at)
        )
        return list(res.scalars())

    async def latest(self, user_id: int, limit: int = 5) -> list[PressureRecord]:
        res = await self.session.execute(
            select(PressureRecord)
            .where(PressureRecord.user_id == user_id)
            .order_by(PressureRecord.measured_at.desc())
            .limit(limit)
        )
        return list(res.scalars())

    async def latest_one(self, user_id: int) -> Optional[PressureRecord]:
        rows = await self.latest(user_id, limit=1)
        return rows[0] if rows else None

    async def delete_for_user(self, user_id: int) -> None:
        await self.session.execute(
            delete(PressureRecord).where(PressureRecord.user_id == user_id)
        )

    async def by_session(
        self, user_id: int, session_uuid: str
    ) -> list[PressureRecord]:
        res = await self.session.execute(
            select(PressureRecord).where(
                and_(
                    PressureRecord.user_id == user_id,
                    PressureRecord.session_uuid == session_uuid,
                )
            ).order_by(PressureRecord.measured_at)
        )
        return list(res.scalars())
