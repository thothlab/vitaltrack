from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InviteToken


class InviteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        inviter_id: int,
        invite_type: str,
        token: str,
        expires_at: datetime,
    ) -> InviteToken:
        obj = InviteToken(
            token=token,
            inviter_id=inviter_id,
            invite_type=invite_type,
            expires_at=expires_at,
        )
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def by_token(self, token: str) -> Optional[InviteToken]:
        res = await self.session.execute(
            select(InviteToken).where(InviteToken.token == token)
        )
        return res.scalar_one_or_none()

    async def mark_used(self, obj: InviteToken, used_by_id: int, when: datetime) -> None:
        obj.used_by_id = used_by_id
        obj.used_at = when
