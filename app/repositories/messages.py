from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Message, MessageThread


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_thread(
        self, doctor_id: int, patient_id: int
    ) -> MessageThread:
        res = await self.session.execute(
            select(MessageThread).where(
                MessageThread.doctor_id == doctor_id,
                MessageThread.patient_id == patient_id,
            )
        )
        thread = res.scalar_one_or_none()
        if thread is None:
            thread = MessageThread(doctor_id=doctor_id, patient_id=patient_id)
            self.session.add(thread)
            await self.session.flush()
        return thread

    async def list_threads_for_doctor(self, doctor_id: int) -> list[MessageThread]:
        res = await self.session.execute(
            select(MessageThread)
            .where(MessageThread.doctor_id == doctor_id)
            .options(selectinload(MessageThread.patient))
            .order_by(MessageThread.last_message_at.desc().nullslast())
        )
        return list(res.scalars())

    async def list_threads_for_patient(self, patient_id: int) -> list[MessageThread]:
        res = await self.session.execute(
            select(MessageThread)
            .where(MessageThread.patient_id == patient_id)
            .options(selectinload(MessageThread.doctor))
        )
        return list(res.scalars())

    async def add_message(
        self, thread: MessageThread, sender_id: int, body: str, when: datetime
    ) -> Message:
        msg = Message(thread_id=thread.id, sender_id=sender_id, body=body)
        self.session.add(msg)
        thread.last_message_at = when
        await self.session.flush()
        return msg

    async def messages(self, thread_id: int, limit: int = 50) -> list[Message]:
        res = await self.session.execute(
            select(Message)
            .where(Message.thread_id == thread_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        rows = list(res.scalars())
        rows.reverse()
        return rows

    async def mark_read(self, thread_id: int, reader_id: int, when: datetime) -> None:
        res = await self.session.execute(
            select(Message).where(
                Message.thread_id == thread_id,
                Message.sender_id != reader_id,
                Message.read_at.is_(None),
            )
        )
        for m in res.scalars():
            m.read_at = when

    async def unread_count(self, thread_id: int, reader_id: int) -> int:
        from sqlalchemy import func as fn
        res = await self.session.execute(
            select(fn.count(Message.id)).where(
                Message.thread_id == thread_id,
                Message.sender_id != reader_id,
                Message.read_at.is_(None),
            )
        )
        return int(res.scalar_one() or 0)

    async def thread_by_id(self, thread_id: int) -> Optional[MessageThread]:
        return await self.session.get(MessageThread, thread_id)
