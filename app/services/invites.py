from __future__ import annotations

import io
import secrets
from datetime import timedelta
from typing import Optional

import qrcode
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InviteToken, User
from app.repositories.invites import InviteRepository
from app.repositories.users import UserRepository
from app.utils.time import now_utc

_TOKEN_TTL_DAYS = 7


def _make_qr(data: str) -> bytes:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class InviteService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = InviteRepository(session)

    async def create_invite(
        self, inviter: User, invite_type: str, bot_username: str
    ) -> tuple[str, bytes]:
        """Create a single-use invite token. Returns (deep_link, qr_png_bytes)."""
        token = secrets.token_urlsafe(32)
        expires_at = now_utc() + timedelta(days=_TOKEN_TTL_DAYS)
        await self.repo.create(inviter.id, invite_type, token, expires_at)
        link = f"https://t.me/{bot_username}?start=inv_{token}"
        return link, _make_qr(link)

    async def redeem(
        self, token: str, redeemer: User
    ) -> Optional[tuple[InviteToken, User]]:
        """Validate and consume a token.
        Returns (invite, inviter) on success, None if invalid/expired/used."""
        invite = await self.repo.by_token(token)
        if invite is None:
            return None
        if invite.used_at is not None:
            return None
        if invite.expires_at < now_utc():
            return None
        if invite.inviter_id == redeemer.id:
            return None  # can't redeem own invite

        inviter = await UserRepository(self.session).by_id(invite.inviter_id)
        if inviter is None:
            return None

        await self.repo.mark_used(invite, redeemer.id, now_utc())
        return invite, inviter
