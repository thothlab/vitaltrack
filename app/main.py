from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, MenuButtonCommands
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.bot.bot import build_bot, build_dispatcher
from app.bot.webhook import build_webhook_router
from app.config import get_settings
from app.logging import configure_logging
from app.scheduler import init_scheduler, shutdown_scheduler

log = logging.getLogger("vitaltrack")

_PATIENT_COMMANDS = [
    BotCommand(command="pressure",      description="Записать давление"),
    BotCommand(command="glucose",       description="Записать глюкозу"),
    BotCommand(command="symptoms",      description="Записать симптомы"),
    BotCommand(command="gi",            description="Записать симптомы ЖКТ"),
    BotCommand(command="headache",      description="Записать приступ головной боли"),
    BotCommand(command="meal",          description="Записать приём пищи"),
    BotCommand(command="labs",          description="Записать анализы"),
    BotCommand(command="med",           description="Отметить приём лекарства"),
    BotCommand(command="meds",          description="Список препаратов"),
    BotCommand(command="report",        description="Получить отчёт"),
    BotCommand(command="history",       description="История измерений"),
    BotCommand(command="invite_doctor", description="Пригласить своего врача"),
    BotCommand(command="invite_friend", description="Пригласить друга как пациента"),
    BotCommand(command="settings",      description="Настройки"),
    BotCommand(command="myid",          description="Мой Telegram ID"),
    BotCommand(command="help",          description="Справка по командам"),
    BotCommand(command="cancel",        description="Отменить ввод"),
    BotCommand(command="forget_me",     description="Удалить мои данные"),
]

_DOCTOR_COMMANDS = [
    BotCommand(command="pressure",         description="Записать давление"),
    BotCommand(command="glucose",          description="Записать глюкозу"),
    BotCommand(command="symptoms",         description="Записать симптомы"),
    BotCommand(command="gi",              description="Записать симптомы ЖКТ"),
    BotCommand(command="headache",        description="Записать приступ головной боли"),
    BotCommand(command="meal",             description="Записать приём пищи"),
    BotCommand(command="labs",             description="Записать анализы"),
    BotCommand(command="med",              description="Отметить приём лекарства"),
    BotCommand(command="meds",             description="Список препаратов"),
    BotCommand(command="report",           description="Получить отчёт"),
    BotCommand(command="history",          description="История измерений"),
    BotCommand(command="invite_patient",   description="Пригласить пациента (привязать к себе)"),
    BotCommand(command="invite_open",      description="Пригласить пациента (без привязки)"),
    BotCommand(command="invite_colleague", description="Пригласить коллегу-врача"),
    BotCommand(command="settings",         description="Настройки"),
    BotCommand(command="myid",             description="Мой Telegram ID"),
    BotCommand(command="help",             description="Справка по командам"),
    BotCommand(command="cancel",           description="Отменить ввод"),
    BotCommand(command="forget_me",        description="Удалить мои данные"),
]


async def _setup_bot_menu(bot: Bot) -> None:
    try:
        await bot.set_my_commands(
            _PATIENT_COMMANDS,
            scope=BotCommandScopeAllPrivateChats(),
        )
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        log.info("Bot command menu configured (%d commands)", len(_PATIENT_COMMANDS))
    except Exception as exc:
        log.warning("Failed to set bot commands: %s", exc)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    bot = build_bot()
    dp = build_dispatcher()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await bot.set_webhook(
            url=settings.webhook_url,
            secret_token=settings.webhook_secret,
            drop_pending_updates=True,
            allowed_updates=dp.resolve_used_update_types(),
        )
        log.info("Webhook set: %s", settings.webhook_url)
        await _setup_bot_menu(bot)
        await init_scheduler()
        try:
            yield
        finally:
            await shutdown_scheduler()
            try:
                await bot.delete_webhook(drop_pending_updates=False)
            except Exception:
                pass
            await bot.session.close()

    app = FastAPI(title="VitalTrack", lifespan=lifespan)
    app.state.bot = bot
    app.state.dispatcher = dp

    app.include_router(
        build_webhook_router(bot, dp, settings.webhook_path, settings.webhook_secret)
    )

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        return JSONResponse({"ok": True})

    return app


app = create_app()
