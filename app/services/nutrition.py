from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MealRecord, User
from app.domain.schemas import MealIn
from app.repositories.nutrition import NutritionRepository


class NutritionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NutritionRepository(session)

    async def add(self, user: User, payload: MealIn) -> MealRecord:
        rec = MealRecord(
            user_id=user.id,
            eaten_at=payload.eaten_at,
            meal_type=payload.meal_type,
            tags=payload.tags,
            note=payload.note,
        )
        return await self.repo.add(rec)
