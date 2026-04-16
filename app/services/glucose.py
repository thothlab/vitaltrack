from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GlucoseRecord, User
from app.domain.schemas import GlucoseIn
from app.repositories.glucose import GlucoseRepository


class GlucoseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = GlucoseRepository(session)

    async def add(self, user: User, payload: GlucoseIn) -> GlucoseRecord:
        rec = GlucoseRecord(
            user_id=user.id,
            measured_at=payload.measured_at,
            value_mmol=payload.value_mmol,
            context=payload.context,
            note=payload.note,
        )
        return await self.repo.add(rec)

    async def latest(self, user: User, limit: int = 5) -> list[GlucoseRecord]:
        return await self.repo.latest(user.id, limit)
