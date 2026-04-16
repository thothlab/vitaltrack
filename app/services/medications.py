from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Medication, MedicationIntake, User
from app.domain.enums import MedScheduleType
from app.domain.schemas import IntakeIn, MedicationIn
from app.repositories.medications import MedicationRepository
from app.utils.time import now_utc, to_user_tz


class MedicationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = MedicationRepository(session)

    async def add(self, user: User, payload: MedicationIn) -> Medication:
        med = Medication(
            user_id=user.id,
            name=payload.name,
            dose=payload.dose,
            notes=payload.notes,
            schedule_type=payload.schedule_type,
            schedule_data=payload.schedule_data,
            starts_on=payload.starts_on or now_utc().date(),
            ends_on=payload.ends_on,
        )
        return await self.repo.add(med)

    async def list_active(self, user: User) -> list[Medication]:
        return await self.repo.list_active(user.id)

    async def deactivate(self, med_id: int) -> None:
        med = await self.repo.by_id(med_id)
        if med is not None:
            await self.repo.deactivate(med)

    async def log_intake(self, user: User, payload: IntakeIn) -> MedicationIntake:
        intake = MedicationIntake(
            user_id=user.id,
            medication_id=payload.medication_id,
            scheduled_at=payload.scheduled_at,
            taken_at=payload.taken_at or now_utc(),
            taken=payload.taken,
            note=payload.note,
        )
        return await self.repo.log_intake(intake)

    async def mark_scheduled(
        self, user: User, medication_id: int, scheduled_at: datetime, taken: bool
    ) -> None:
        await self.repo.upsert_intake(
            user_id=user.id,
            medication_id=medication_id,
            scheduled_at=scheduled_at,
            taken_at=now_utc() if taken else None,
            taken=taken,
        )

    # ----- adherence -----
    async def adherence(
        self, user: User, start: datetime, end: datetime
    ) -> dict[int, dict]:
        meds = await self.repo.list_active(user.id)
        intakes = await self.repo.intakes_between(user.id, start, end)
        scheduled_by_med = self.expected_intakes(meds, start, end, user.timezone)

        out: dict[int, dict] = {}
        intakes_by_med: dict[int, list[MedicationIntake]] = {}
        for ix in intakes:
            intakes_by_med.setdefault(ix.medication_id, []).append(ix)

        for med in meds:
            scheduled = scheduled_by_med.get(med.id, [])
            taken_keys = {
                ix.scheduled_at for ix in intakes_by_med.get(med.id, []) if ix.taken
            }
            taken = sum(1 for s in scheduled if s in taken_keys)
            total = len(scheduled)
            out[med.id] = {
                "medication": med,
                "expected": total,
                "taken": taken,
                "missed": max(total - taken, 0),
                "rate": (taken / total) if total else None,
            }
        return out

    @staticmethod
    def expected_intakes(
        meds: Iterable[Medication],
        start: datetime,
        end: datetime,
        tz_name: str,
    ) -> dict[int, list[datetime]]:
        out: dict[int, list[datetime]] = {}
        for med in meds:
            if med.schedule_type == MedScheduleType.AS_NEEDED:
                out[med.id] = []
                continue
            slots: list[datetime] = []
            cur = start
            while cur < end:
                local = to_user_tz(cur, tz_name)
                if med.schedule_type == MedScheduleType.FIXED_TIMES:
                    times = med.schedule_data.get("times", [])
                    for t in times:
                        hh, mm = (int(x) for x in t.split(":"))
                        local_slot = local.replace(
                            hour=hh, minute=mm, second=0, microsecond=0
                        )
                        utc_slot = local_slot.astimezone(timezone.utc)
                        if start <= utc_slot < end:
                            slots.append(utc_slot)
                cur = (local + timedelta(days=1)).astimezone(timezone.utc)
                cur = cur.replace(hour=0, minute=0, second=0, microsecond=0)

            if med.schedule_type == MedScheduleType.EVERY_N_HOURS:
                interval = int(med.schedule_data.get("interval_hours", 8))
                anchor = med.schedule_data.get("anchor", "08:00")
                hh, mm = (int(x) for x in anchor.split(":"))
                base = to_user_tz(start, tz_name).replace(
                    hour=hh, minute=mm, second=0, microsecond=0
                )
                if base.astimezone(timezone.utc) > start:
                    base -= timedelta(days=1)
                cur_local = base
                while cur_local.astimezone(timezone.utc) < end:
                    if cur_local.astimezone(timezone.utc) >= start:
                        slots.append(cur_local.astimezone(timezone.utc))
                    cur_local += timedelta(hours=interval)

            slots.sort()
            out[med.id] = slots
        return out
