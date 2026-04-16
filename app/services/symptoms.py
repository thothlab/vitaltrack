from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SymptomRecord, User
from app.domain.schemas import SymptomIn
from app.repositories.symptoms import SymptomRepository


class SymptomService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SymptomRepository(session)

    async def add(self, user: User, payload: SymptomIn) -> SymptomRecord:
        rec = SymptomRecord(
            user_id=user.id,
            occurred_at=payload.occurred_at,
            wellbeing=payload.wellbeing,
            symptoms=payload.symptoms,
            intensity=payload.intensity,
            note=payload.note,
        )
        return await self.repo.add(rec)
