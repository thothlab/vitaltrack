from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HeadacheAttack


class HeadacheRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, attack: HeadacheAttack) -> HeadacheAttack:
        self.session.add(attack)
        await self.session.flush()
        return attack

    async def latest(self, user_id: int, limit: int = 10) -> list[HeadacheAttack]:
        res = await self.session.execute(
            select(HeadacheAttack)
            .where(HeadacheAttack.user_id == user_id)
            .order_by(HeadacheAttack.started_at.desc())
            .limit(limit)
        )
        return list(res.scalars())

    async def list_between(
        self, user_id: int, start: datetime, end: datetime
    ) -> list[HeadacheAttack]:
        res = await self.session.execute(
            select(HeadacheAttack)
            .where(
                and_(
                    HeadacheAttack.user_id == user_id,
                    HeadacheAttack.started_at >= start,
                    HeadacheAttack.started_at < end,
                )
            )
            .order_by(HeadacheAttack.started_at)
        )
        return list(res.scalars())
