from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from app.services.users import UserService


class UserMiddleware(BaseMiddleware):
    """Resolve the authenticated User and attach to handler context."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session = data.get("session")
        if session is None:
            return await handler(event, data)

        tg_user = None
        if isinstance(event, Update):
            if event.message:
                tg_user = event.message.from_user
            elif event.callback_query:
                tg_user = event.callback_query.from_user
            elif event.edited_message:
                tg_user = event.edited_message.from_user
            elif event.my_chat_member:
                tg_user = event.my_chat_member.from_user
        elif isinstance(event, (Message, CallbackQuery)):
            tg_user = event.from_user

        if tg_user is not None:
            svc = UserService(session)
            full_name = " ".join(
                part for part in [tg_user.first_name, tg_user.last_name] if part
            ).strip() or None
            user = await svc.ensure_user(
                telegram_id=tg_user.id,
                username=tg_user.username,
                full_name=full_name,
            )
            data["user"] = user
        return await handler(event, data)
