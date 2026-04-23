from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import BotCommand, BotCommandScopeChat, BufferedInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.patient import main_menu
from app.db.models import User
from app.domain.enums import UserRole
from app.services.invites import InviteService

router = Router(name="invite")

_TTL_DAYS = 7


async def _send_qr(
    message: Message,
    session: AsyncSession,
    user: User,
    bot: Bot,
    invite_type: str,
    caption: str,
) -> None:
    bot_me = await bot.get_me()
    svc = InviteService(session)
    link, qr_bytes = await svc.create_invite(user, invite_type, bot_me.username)
    await message.answer_photo(
        BufferedInputFile(qr_bytes, filename="invite.png"),
        caption=f"{caption}\n\nСсылка: {link}\n\nДействует {_TTL_DAYS} дней.",
    )


# ─── patient: invite their doctor ────────────────────────────────────────────

@router.message(Command("invite_doctor"))
async def cmd_invite_doctor(
    message: Message, session: AsyncSession, user: User, bot: Bot
) -> None:
    if user.role == UserRole.DOCTOR:
        await message.answer(
            "Вы врач. Для приглашения пациента — /invite_patient, "
            "для приглашения коллеги-врача — /invite_colleague"
        )
        return
    if user.doctor_id is not None:
        await message.answer(
            "Вы уже прикреплены к врачу. "
            "Пациент может работать только с одним врачом одновременно."
        )
        return
    await _send_qr(
        message, session, user, bot, "doctor",
        "QR-код для вашего врача.\n"
        "Врач сканирует код — и сразу будет привязан к вам.",
    )


# ─── patient: referral link for a friend (new patient, no doctor yet) ────────

@router.message(Command("invite_friend"))
async def cmd_invite_friend(
    message: Message, session: AsyncSession, user: User, bot: Bot
) -> None:
    if user.role == UserRole.DOCTOR:
        await message.answer("Реферальная ссылка для пациентов. Вам доступно /invite_patient")
        return
    await _send_qr(
        message, session, user, bot, "referral",
        "Реферальная ссылка для друга.\n"
        "Друг откроет ссылку, зарегистрируется как пациент и сможет пригласить своего врача.",
    )


# ─── doctor: invite a patient (no doctor linkage) ────────────────────────────

@router.message(Command("invite_open"))
async def cmd_invite_open(
    message: Message, session: AsyncSession, user: User, bot: Bot
) -> None:
    if user.role != UserRole.DOCTOR:
        await message.answer("Эта команда доступна только врачам.")
        return
    await _send_qr(
        message, session, user, bot, "referral",
        "QR-код для нового пациента (без привязки к врачу).\n"
        "Пациент зарегистрируется и сможет пригласить своего врача самостоятельно.",
    )


# ─── doctor: invite a patient (linked to this doctor) ─────────────────────────

@router.message(Command("invite_patient"))
async def cmd_invite_patient(
    message: Message, session: AsyncSession, user: User, bot: Bot
) -> None:
    if user.role != UserRole.DOCTOR:
        await message.answer(
            "Эта команда доступна только врачам. "
            "Для приглашения врача используйте /invite_doctor"
        )
        return
    await _send_qr(
        message, session, user, bot, "patient",
        "QR-код для вашего пациента.\n"
        "Пациент сканирует код — и сразу будет привязан к вам.",
    )


# ─── doctor: invite a colleague ───────────────────────────────────────────────

@router.message(Command("invite_colleague"))
async def cmd_invite_colleague(
    message: Message, session: AsyncSession, user: User, bot: Bot
) -> None:
    if user.role != UserRole.DOCTOR:
        await message.answer("Эта команда доступна только врачам.")
        return
    await _send_qr(
        message, session, user, bot, "colleague",
        "QR-код для коллеги-врача.\n"
        "Коллега сканирует код — и получает доступ к боту как врач.",
    )


# ─── deep-link redemption (called from start handler) ─────────────────────────

async def process_invite_token(
    message: Message,
    token: str,
    user: User,
    session: AsyncSession,
    bot: Bot,
) -> None:
    svc = InviteService(session)
    result = await svc.redeem(token, user)

    if result.error:
        await message.answer(
            f"❌ {result.error}",
            reply_markup=main_menu(is_doctor=(user.role == UserRole.DOCTOR)),
        )
        return

    invite, inviter = result.invite, result.inviter

    if invite.invite_type == "doctor":
        # Redeemer becomes doctor; inviter (patient) gets linked.
        user.role = UserRole.DOCTOR
        inviter.doctor_id = user.id
        await message.answer(
            f"✅ Вы подключены как врач пациента "
            f"<b>{inviter.full_name or inviter.telegram_id}</b>.",
            reply_markup=main_menu(is_doctor=True),
        )
        _notify(bot, inviter.telegram_id,
                f"✅ Врач <b>{user.full_name or user.telegram_id}</b> "
                "принял ваше приглашение и теперь видит ваши показатели.")
        await _set_doctor_commands(bot, user.telegram_id)

    elif invite.invite_type == "colleague":
        # Redeemer becomes doctor; no patient linkage.
        user.role = UserRole.DOCTOR
        await message.answer(
            f"✅ Вы зарегистрированы как врач.\n"
            f"Пригласил: <b>{inviter.full_name or inviter.telegram_id}</b>.",
            reply_markup=main_menu(is_doctor=True),
        )
        _notify(bot, inviter.telegram_id,
                f"✅ Коллега <b>{user.full_name or user.telegram_id}</b> "
                "принял ваше приглашение и зарегистрирован как врач.")
        await _set_doctor_commands(bot, user.telegram_id)

    elif invite.invite_type == "patient":
        # Redeemer becomes patient of inviter (doctor).
        user.doctor_id = inviter.id
        await message.answer(
            f"✅ Вы подключены к врачу "
            f"<b>{inviter.full_name or inviter.telegram_id}</b>.",
            reply_markup=main_menu(is_doctor=False),
        )
        _notify(bot, inviter.telegram_id,
                f"✅ Пациент <b>{user.full_name or user.telegram_id}</b> "
                "принял ваше приглашение.")

    elif invite.invite_type == "referral":
        # Redeemer registers as patient; no doctor yet.
        await message.answer(
            f"✅ Вы зарегистрированы как пациент.\n"
            "Чтобы пригласить своего врача, используйте /invite_doctor.",
            reply_markup=main_menu(is_doctor=False),
        )
        _notify(bot, inviter.telegram_id,
                f"✅ Ваш друг <b>{user.full_name or user.telegram_id}</b> "
                "зарегистрировался по вашей реферальной ссылке.")


def _notify(bot: Bot, chat_id: int, text: str) -> None:
    import asyncio
    asyncio.ensure_future(bot.send_message(chat_id, text))


async def _set_doctor_commands(bot: Bot, telegram_id: int) -> None:
    from app.main import _DOCTOR_COMMANDS
    try:
        await bot.set_my_commands(
            _DOCTOR_COMMANDS,
            scope=BotCommandScopeChat(chat_id=telegram_id),
        )
    except Exception:
        pass
