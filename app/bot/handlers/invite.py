from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import BotCommand, BufferedInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.patient import main_menu
from app.db.models import User
from app.domain.enums import UserRole
from app.services.invites import InviteService

router = Router(name="invite")


@router.message(Command("invite_doctor"))
async def cmd_invite_doctor(
    message: Message, session: AsyncSession, user: User, bot: Bot
) -> None:
    if user.role == UserRole.DOCTOR:
        await message.answer(
            "Вы врач. Для приглашения пациента используйте /invite_patient"
        )
        return
    bot_me = await bot.get_me()
    svc = InviteService(session)
    link, qr_bytes = await svc.create_invite(user, "doctor", bot_me.username)
    await message.answer_photo(
        BufferedInputFile(qr_bytes, filename="invite_doctor.png"),
        caption=(
            "QR-код для подключения врача.\n\n"
            f"Ссылка: {link}\n\n"
            "Врач сканирует код или открывает ссылку — и сразу будет привязан к вам. "
            f"Действует {7} дней."
        ),
    )


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
    bot_me = await bot.get_me()
    svc = InviteService(session)
    link, qr_bytes = await svc.create_invite(user, "patient", bot_me.username)
    await message.answer_photo(
        BufferedInputFile(qr_bytes, filename="invite_patient.png"),
        caption=(
            "QR-код для подключения пациента.\n\n"
            f"Ссылка: {link}\n\n"
            "Пациент сканирует код или открывает ссылку — и будет привязан к вам. "
            f"Действует {7} дней."
        ),
    )


async def process_invite_token(
    message: Message,
    token: str,
    user: User,
    session: AsyncSession,
    bot: Bot,
) -> None:
    """Called from start handler after consent is granted."""
    from aiogram.types import BotCommand, BotCommandScopeChat

    svc = InviteService(session)
    result = await svc.redeem(token, user)

    if result is None:
        await message.answer(
            "Ссылка недействительна, уже использована или истёк срок действия.",
            reply_markup=main_menu(is_doctor=(user.role == UserRole.DOCTOR)),
        )
        return

    invite, inviter = result

    if invite.invite_type == "doctor":
        # Redeemer (current user) becomes the doctor; inviter is the patient.
        user.role = UserRole.DOCTOR
        inviter.doctor_id = user.id
        await message.answer(
            f"✅ Вы подключены как врач пациента "
            f"<b>{inviter.full_name or inviter.telegram_id}</b>.\n"
            "Теперь вы можете просматривать его данные.",
            reply_markup=main_menu(is_doctor=True),
        )
        try:
            await bot.send_message(
                inviter.telegram_id,
                f"✅ Врач <b>{user.full_name or user.telegram_id}</b> "
                "принял ваше приглашение и теперь видит ваши показатели.",
            )
        except Exception:
            pass
        # Update doctor's command menu to show /invite_patient instead of /invite_doctor
        try:
            from aiogram.types import BotCommandScopeChat
            from app.main import _DOCTOR_COMMANDS
            await bot.set_my_commands(
                _DOCTOR_COMMANDS,
                scope=BotCommandScopeChat(chat_id=user.telegram_id),
            )
        except Exception:
            pass

    elif invite.invite_type == "patient":
        # Redeemer (current user) is the patient; inviter is the doctor.
        user.doctor_id = inviter.id
        await message.answer(
            f"✅ Вы подключены к врачу "
            f"<b>{inviter.full_name or inviter.telegram_id}</b>.",
            reply_markup=main_menu(is_doctor=(user.role == UserRole.DOCTOR)),
        )
        try:
            await bot.send_message(
                inviter.telegram_id,
                f"✅ Пациент <b>{user.full_name or user.telegram_id}</b> "
                "принял ваше приглашение.",
            )
        except Exception:
            pass
