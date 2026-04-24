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
        commands,
        doctor,
        gi,
        glucose,
        headache,
        invite,
        labs,
        medications,
        menu,
        nutrition,
        pressure,
        profile,
        reports,
        settings as settings_handler,
        start,
        symptoms,
    )

    for router in (
        start.router,
        invite.router,    # before menu so /invite_* commands are caught early
        commands.router,  # shortcut commands before FSM-owning routers
        menu.router,
        pressure.router,
        glucose.router,
        medications.router,
        symptoms.router,
        gi.router,
        headache.router,
        nutrition.router,
        labs.router,
        reports.router,
        doctor.router,
        calculators.router,
        profile.router,      # must precede settings.router to own set:profile
        settings_handler.router,
    ):
        dp.include_router(router)

    return dp
