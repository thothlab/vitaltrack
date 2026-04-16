from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LabResult, User
from app.domain.schemas import LabIn
from app.repositories.labs import LabRepository


class LabService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = LabRepository(session)

    async def add(self, user: User, payload: LabIn) -> LabResult:
        rec = LabResult(
            user_id=user.id,
            drawn_at=payload.drawn_at,
            total_chol=payload.total_chol,
            ldl=payload.ldl,
            hdl=payload.hdl,
            triglycerides=payload.triglycerides,
            glucose_fasting=payload.glucose_fasting,
            insulin_fasting=payload.insulin_fasting,
            creatinine_umol=payload.creatinine_umol,
            note=payload.note,
        )
        return await self.repo.add(rec)
