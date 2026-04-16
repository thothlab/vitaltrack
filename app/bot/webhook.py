from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import APIRouter, Header, HTTPException, Request

log = logging.getLogger(__name__)


def build_webhook_router(bot: Bot, dp: Dispatcher, path: str, secret: str) -> APIRouter:
    router = APIRouter()

    @router.post(path)
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ) -> dict:
        if secret and x_telegram_bot_api_secret_token != secret:
            raise HTTPException(status_code=401, detail="bad secret")
        payload = await request.json()
        update = Update.model_validate(payload)
        await dp.feed_update(bot, update)
        return {"ok": True}

    return router
