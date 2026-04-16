from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.bot.bot import build_bot, build_dispatcher
from app.bot.webhook import build_webhook_router
from app.config import get_settings
from app.logging import configure_logging
from app.scheduler import init_scheduler, shutdown_scheduler

log = logging.getLogger("vitaltrack")


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
