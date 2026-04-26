"""Job entrypoints invoked by APScheduler.

These functions must be importable by dotted path (used in job args). They
acquire their own DB session and Bot instance — they do not rely on FastAPI
state.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from app.config import get_settings
from app.db.models import Medication, User
from app.db.session import async_session_factory
from app.domain.enums import UserRole
from app.repositories.alerts import AlertRepository
from app.repositories.users import UserRepository
from app.services.alerts import AlertService
from app.utils.time import now_utc

log = logging.getLogger(__name__)


async def _bot() -> Bot:
    settings = get_settings()
    return Bot(settings.bot_token)


async def fire_med_reminder(telegram_id: int, medication_id: int, slot_label: str) -> None:
    """Send a 'time to take meds' message to the user with quick-actions."""
    bot = await _bot()
    try:
        async with async_session_factory() as session:
            med = await session.get(Medication, medication_id)
            user = (await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )).scalar_one_or_none()
            if med is None or user is None or not med.is_active:
                return
            slot_dt = _slot_to_utc(slot_label, user.timezone)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Принял",
                        callback_data=f"med_take:{medication_id}:{slot_dt.isoformat()}",
                    ),
                    InlineKeyboardButton(
                        text="⏭ Пропустить",
                        callback_data=f"med_skip:{medication_id}:{slot_dt.isoformat()}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🚫 Остановить",
                        callback_data=f"med_stop:{medication_id}",
                    ),
                ],
            ])
            text = f"💊 Время принять «{med.name}»"
            if med.dose:
                text += f" ({med.dose})"
            try:
                await bot.send_message(user.telegram_id, text, reply_markup=kb)
            except Exception as e:
                log.warning("Failed to send reminder to %s: %s", telegram_id, e)
    finally:
        await bot.session.close()


def _slot_to_utc(slot_label: str, tz_name: str) -> datetime:
    from zoneinfo import ZoneInfo
    hh, mm = (int(x) for x in slot_label.split(":"))
    tz = ZoneInfo(tz_name)
    today_local = datetime.now(tz=tz).replace(hour=hh, minute=mm, second=0, microsecond=0)
    return today_local.astimezone(timezone.utc)


async def run_no_data_watchdog() -> None:
    bot = await _bot()
    try:
        async with async_session_factory() as session:
            users = (await session.execute(
                select(User).where(User.role == UserRole.PATIENT, User.deleted_at.is_(None))
            )).scalars().all()
            asvc = AlertService(session)
            for user in users:
                fired = await asvc.detect_no_data(user)
                if fired:
                    await _notify_alert(bot, session, user, fired["summary"])
            await session.commit()
    finally:
        await bot.session.close()


async def run_missed_med_watchdog() -> None:
    bot = await _bot()
    try:
        async with async_session_factory() as session:
            users = (await session.execute(
                select(User).where(User.role == UserRole.PATIENT, User.deleted_at.is_(None))
            )).scalars().all()
            asvc = AlertService(session)
            for user in users:
                fired = await asvc.detect_missed_meds(user)
                for f in fired:
                    await _notify_alert(bot, session, user, f["summary"])
            await session.commit()
    finally:
        await bot.session.close()


_GREETING_TEXTS = {
    "morning": (
        "🌅 Доброе утро! Как твоё самочувствие?\n"
        "Не забудь внести данные:\n"
        "• Давление: /pressure\n"
        "• Глюкоза: /glucose\n"
        "• Симптомы: /symptoms\n"
        "• Питание: /meal\n"
        "• Лекарства: /med"
    ),
    "afternoon": (
        "☀️ Как твоё самочувствие?\n"
        "Не забудь внести данные:\n"
        "• Давление: /pressure\n"
        "• Глюкоза: /glucose\n"
        "• Симптомы: /symptoms\n"
        "• Питание: /meal\n"
        "• Лекарства: /med"
    ),
    "evening": (
        "🌙 Добрый вечер! Как прошёл день?\n"
        "Не забудь внести данные:\n"
        "• Давление: /pressure\n"
        "• Глюкоза: /glucose\n"
        "• Симптомы: /symptoms\n"
        "• Питание: /meal\n"
        "• Лекарства: /med"
    ),
}


async def fire_greeting(telegram_id: int, period: str) -> None:
    """Send a check-in prompt (morning / afternoon / evening) to one patient."""
    bot = await _bot()
    text = _GREETING_TEXTS.get(period, _GREETING_TEXTS["morning"])
    try:
        await bot.send_message(telegram_id, text)
    except Exception as e:
        log.warning("Greeting (%s) failed for %s: %s", period, telegram_id, e)
    finally:
        await bot.session.close()


async def _notify_alert(bot: Bot, session, user: User, text: str) -> None:
    try:
        await bot.send_message(user.telegram_id, f"⚠️ {text}")
    except Exception as e:
        log.warning("Cannot deliver alert to user %s: %s", user.id, e)
    if user.doctor_id:
        doctor = await session.get(User, user.doctor_id)
        if doctor:
            try:
                await bot.send_message(
                    doctor.telegram_id,
                    f"⚠️ Пациент {user.full_name or user.username or user.telegram_id}: {text}",
                )
            except Exception as e:
                log.warning("Cannot deliver alert to doctor %s: %s", doctor.id, e)
