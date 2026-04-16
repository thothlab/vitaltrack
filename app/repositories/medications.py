from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Medication, MedicationIntake


class MedicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, med: Medication) -> Medication:
        self.session.add(med)
        await self.session.flush()
        return med

    async def by_id(self, med_id: int) -> Optional[Medication]:
        return await self.session.get(Medication, med_id)

    async def list_active(self, user_id: int) -> list[Medication]:
        res = await self.session.execute(
            select(Medication).where(
                Medication.user_id == user_id, Medication.is_active.is_(True)
            ).order_by(Medication.name)
        )
        return list(res.scalars())

    async def deactivate(self, med: Medication) -> None:
        med.is_active = False

    # ---- intakes ----
    async def log_intake(self, intake: MedicationIntake) -> MedicationIntake:
        self.session.add(intake)
        await self.session.flush()
        return intake

    async def upsert_intake(
        self,
        *,
        user_id: int,
        medication_id: int,
        scheduled_at: datetime,
        taken_at: Optional[datetime],
        taken: bool,
    ) -> None:
        """Idempotent for (medication_id, scheduled_at)."""
        stmt = (
            insert(MedicationIntake)
            .values(
                user_id=user_id,
                medication_id=medication_id,
                scheduled_at=scheduled_at,
                taken_at=taken_at,
                taken=taken,
            )
            .on_conflict_do_update(
                index_elements=["medication_id", "scheduled_at"],
                set_={"taken_at": taken_at, "taken": taken},
            )
        )
        await self.session.execute(stmt)

    async def intakes_between(
        self, user_id: int, start: datetime, end: datetime
    ) -> list[MedicationIntake]:
        res = await self.session.execute(
            select(MedicationIntake)
            .where(
                and_(
                    MedicationIntake.user_id == user_id,
                    MedicationIntake.scheduled_at >= start,
                    MedicationIntake.scheduled_at < end,
                )
            )
            .order_by(MedicationIntake.scheduled_at)
        )
        return list(res.scalars())

    async def last_intake(
        self, user_id: int, medication_id: int
    ) -> Optional[MedicationIntake]:
        res = await self.session.execute(
            select(MedicationIntake)
            .where(
                MedicationIntake.user_id == user_id,
                MedicationIntake.medication_id == medication_id,
                MedicationIntake.taken.is_(True),
            )
            .order_by(MedicationIntake.taken_at.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()
