from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Reminder


class ReminderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, reminder: Reminder) -> Reminder:
        self.session.add(reminder)
        await self.session.flush()
        return reminder

    async def by_id(self, reminder_id: int) -> Optional[Reminder]:
        return await self.session.get(Reminder, reminder_id)

    async def list_active(self) -> list[Reminder]:
        res = await self.session.execute(
            select(Reminder).where(Reminder.is_active.is_(True))
        )
        return list(res.scalars())

    async def list_for_user(self, user_id: int) -> list[Reminder]:
        res = await self.session.execute(
            select(Reminder).where(Reminder.user_id == user_id)
        )
        return list(res.scalars())

    async def list_for_medication(self, medication_id: int) -> list[Reminder]:
        res = await self.session.execute(
            select(Reminder).where(Reminder.medication_id == medication_id)
        )
        return list(res.scalars())

    async def deactivate(self, reminder: Reminder) -> None:
        reminder.is_active = False
