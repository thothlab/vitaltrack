from __future__ import annotations

import io
import secrets
from datetime import timedelta
from typing import NamedTuple, Optional

import qrcode
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InviteToken, User
from app.repositories.invites import InviteRepository
from app.repositories.users import UserRepository
from app.utils.time import now_utc

_TOKEN_TTL_DAYS = 7


class RedeemResult(NamedTuple):
    invite: Optional[InviteToken]
    inviter: Optional[User]
    error: Optional[str]  # None = success


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

    async def redeem(self, token: str, redeemer: User) -> RedeemResult:
        """Validate and consume a token. Returns RedeemResult; error=None means success."""
        invite = await self.repo.by_token(token)
        if invite is None:
            return RedeemResult(None, None, "Ссылка не найдена — возможно, она была удалена.")
        if invite.used_at is not None:
            return RedeemResult(None, None, "Ссылка уже была использована ранее.")
        if invite.expires_at < now_utc():
            return RedeemResult(None, None, "Срок действия ссылки истёк. Попросите выслать новую.")
        if invite.inviter_id == redeemer.id:
            return RedeemResult(
                None, None,
                "Вы не можете использовать собственную ссылку-приглашение.\n"
                "Перешлите её другому человеку — врачу или пациенту."
            )
        # A patient may be linked to only one doctor.
        if invite.invite_type == "doctor" and redeemer.doctor_id is not None:
            return RedeemResult(
                None, None,
                "Вы уже прикреплены к врачу. "
                "Пациент может работать только с одним врачом одновременно."
            )

        inviter = await UserRepository(self.session).by_id(invite.inviter_id)
        if inviter is None:
            return RedeemResult(None, None, "Пригласивший пользователь не найден.")

        await self.repo.mark_used(invite, redeemer.id, now_utc())
        return RedeemResult(invite, inviter, None)
