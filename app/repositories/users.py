from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.domain.enums import UserRole


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def by_id(self, user_id: int) -> Optional[User]:
        return await self.session.get(User, user_id)

    async def by_telegram(self, telegram_id: int) -> Optional[User]:
        res = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        return res.scalar_one_or_none()

    async def list_doctors(self) -> list[User]:
        res = await self.session.execute(select(User).where(User.role == UserRole.DOCTOR))
        return list(res.scalars())

    async def list_patients_for_doctor(self, doctor_id: int) -> list[User]:
        res = await self.session.execute(
            select(User).where(User.doctor_id == doctor_id).order_by(User.full_name)
        )
        return list(res.scalars())

    async def list_all_patients(self) -> list[User]:
        res = await self.session.execute(
            select(User).where(User.role == UserRole.PATIENT, User.deleted_at.is_(None))
        )
        return list(res.scalars())

    async def upsert_from_telegram(
        self,
        telegram_id: int,
        username: Optional[str],
        full_name: Optional[str],
        role: UserRole,
        timezone: str,
    ) -> User:
        user = await self.by_telegram(telegram_id)
        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                role=role,
                timezone=timezone,
            )
            self.session.add(user)
            await self.session.flush()
        else:
            user.username = username or user.username
            user.full_name = full_name or user.full_name
            if user.role != UserRole.DOCTOR and role == UserRole.DOCTOR:
                user.role = role
        return user

    async def set_consent(self, user: User, when: datetime) -> None:
        user.consent_at = when

    async def soft_delete(self, user: User, when: datetime) -> None:
        user.deleted_at = when

    async def attach_doctor(self, patient: User, doctor: User) -> None:
        patient.doctor_id = doctor.id
