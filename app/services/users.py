from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import User
from app.domain.enums import UserRole
from app.repositories.glucose import GlucoseRepository
from app.repositories.labs import LabRepository
from app.repositories.medications import MedicationRepository
from app.repositories.messages import MessageRepository
from app.repositories.nutrition import NutritionRepository
from app.repositories.pressure import PressureRepository
from app.repositories.symptoms import SymptomRepository
from app.repositories.users import UserRepository
from app.utils.time import now_utc


class PermissionError_(PermissionError):
    pass


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)
        self.settings = get_settings()

    async def ensure_user(
        self,
        telegram_id: int,
        username: Optional[str],
        full_name: Optional[str],
    ) -> User:
        role = (
            UserRole.DOCTOR
            if telegram_id in self.settings.doctor_ids
            else UserRole.PATIENT
        )
        user = await self.repo.upsert_from_telegram(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            role=role,
            timezone=self.settings.app_timezone,
        )
        return user

    async def grant_consent(self, user: User) -> None:
        await self.repo.set_consent(user, now_utc())

    async def attach_patient_to_doctor(self, patient: User, doctor: User) -> None:
        if doctor.role != UserRole.DOCTOR:
            raise PermissionError_("user is not a doctor")
        await self.repo.attach_doctor(patient, doctor)

    async def forget_patient(self, user: User) -> None:
        """Hard delete all patient medical data, then soft-delete the user."""
        # Cascade is configured at ORM level for medical tables;
        # explicit deletes for clarity & audit.
        await PressureRepository(self.session).delete_for_user(user.id)
        # Other tables fall under cascade via ORM relationship; flush:
        await self.repo.soft_delete(user, now_utc())

    async def list_patients_for(self, doctor: User) -> list[User]:
        if doctor.role != UserRole.DOCTOR:
            raise PermissionError_("user is not a doctor")
        return await self.repo.list_patients_for_doctor(doctor.id)

    async def by_telegram(self, telegram_id: int) -> Optional[User]:
        return await self.repo.by_telegram(telegram_id)

    async def update_profile(self, user: User, **fields: object) -> None:
        """Patch the patient profile in-place. Only known columns are
        accepted; values of None clear the field. Used by the in-bot
        profile wizard."""
        allowed = {
            "sex", "birth_date", "height_cm", "weight_kg",
            "is_smoker", "has_diabetes",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"unknown profile field(s): {sorted(unknown)}")
        for key, value in fields.items():
            setattr(user, key, value)
