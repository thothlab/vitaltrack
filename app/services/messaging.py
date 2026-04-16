from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message, MessageThread, User
from app.domain.enums import UserRole
from app.repositories.messages import MessageRepository
from app.utils.time import now_utc


class MessagingService:
    """In-bot doctor↔patient inbox (NOT real Telegram chats)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = MessageRepository(session)

    async def open_thread(self, doctor: User, patient: User) -> MessageThread:
        if doctor.role != UserRole.DOCTOR or patient.role != UserRole.PATIENT:
            raise PermissionError("invalid roles for thread")
        return await self.repo.get_or_create_thread(doctor.id, patient.id)

    async def send(
        self, thread: MessageThread, sender: User, body: str
    ) -> Message:
        if sender.id not in (thread.doctor_id, thread.patient_id):
            raise PermissionError("sender not in thread")
        return await self.repo.add_message(thread, sender.id, body, now_utc())

    async def threads_for(self, user: User) -> list[MessageThread]:
        if user.role == UserRole.DOCTOR:
            return await self.repo.list_threads_for_doctor(user.id)
        return await self.repo.list_threads_for_patient(user.id)

    async def messages(self, thread_id: int, reader: User, limit: int = 50) -> list[Message]:
        msgs = await self.repo.messages(thread_id, limit)
        await self.repo.mark_read(thread_id, reader.id, now_utc())
        return msgs

    async def unread_count(self, thread_id: int, reader: User) -> int:
        return await self.repo.unread_count(thread_id, reader.id)

    async def thread(self, thread_id: int) -> Optional[MessageThread]:
        return await self.repo.thread_by_id(thread_id)
