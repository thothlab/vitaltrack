from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from app.bot.middlewares.db import DBSessionMiddleware
from app.bot.middlewares.user import UserMiddleware
from app.config import get_settings


def build_bot() -> Bot:
    settings = get_settings()
    return Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def build_dispatcher() -> Dispatcher:
    settings = get_settings()
    storage = RedisStorage.from_url(settings.redis_url)
    dp = Dispatcher(storage=storage)

    dp.update.middleware(DBSessionMiddleware())
    dp.update.middleware(UserMiddleware())

    # register routers
    from app.bot.handlers import (
        calculators,
        doctor,
        glucose,
        labs,
        medications,
        menu,
        nutrition,
        pressure,
        reports,
        settings as settings_handler,
        start,
        symptoms,
    )

    for router in (
        start.router,
        menu.router,
        pressure.router,
        glucose.router,
        medications.router,
        symptoms.router,
        nutrition.router,
        labs.router,
        reports.router,
        doctor.router,
        calculators.router,
        settings_handler.router,
    ):
        dp.include_router(router)

    return dp
