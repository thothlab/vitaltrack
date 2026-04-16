from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PressureRecord, User
from app.domain.schemas import PressureIn
from app.repositories.pressure import PressureRepository


class PressureService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = PressureRepository(session)

    async def add(self, user: User, payload: PressureIn) -> PressureRecord:
        rec = PressureRecord(
            user_id=user.id,
            measured_at=payload.measured_at,
            systolic=payload.systolic,
            diastolic=payload.diastolic,
            pulse=payload.pulse,
            arm=payload.arm,
            session_uuid=payload.session_uuid,
            note=payload.note,
        )
        return await self.repo.add(rec)

    async def latest(self, user: User, limit: int = 5) -> list[PressureRecord]:
        return await self.repo.latest(user.id, limit)
