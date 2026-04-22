from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import consent_kb
from app.bot.keyboards.patient import main_menu
from app.db.models import User
from app.domain.enums import UserRole
from app.services.users import UserService
from app.utils.i18n import t

router = Router(name="start")

_INV_PREFIX = "inv_"


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    bot: Bot,
) -> None:
    await state.clear()

    # Deep-link invite payload: /start inv_<token>
    if command.args and command.args.startswith(_INV_PREFIX):
        token = command.args[len(_INV_PREFIX):]
        if user.consent_at is None:
            # Ask for consent first; process invite after it's granted.
            await state.update_data(pending_invite=token)
            await message.answer(t("consent_request"), reply_markup=consent_kb())
            return
        from app.bot.handlers.invite import process_invite_token
        await process_invite_token(message, token, user, session, bot)
        return

    if user.consent_at is None:
        await message.answer(t("consent_request"), reply_markup=consent_kb())
        return
    await message.answer(
        f"Здравствуйте, {user.full_name or ''}! Я VitalTrack — ваш медицинский "
        f"дневник. Выберите действие:",
        reply_markup=main_menu(is_doctor=(user.role == UserRole.DOCTOR)),
    )


@router.callback_query(F.data == "consent:yes")
async def on_consent_yes(
    cq: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    bot: Bot,
) -> None:
    await UserService(session).grant_consent(user)

    data = await state.get_data()
    pending_invite = data.get("pending_invite")
    await state.clear()

    if pending_invite:
        await cq.message.edit_text(t("consent_granted"))
        from app.bot.handlers.invite import process_invite_token
        await process_invite_token(cq.message, pending_invite, user, session, bot)
        await cq.answer()
        return

    await cq.message.edit_text(t("consent_granted"))
    await cq.message.answer(
        "Главное меню:",
        reply_markup=main_menu(is_doctor=(user.role == UserRole.DOCTOR)),
    )
    await cq.answer()


@router.callback_query(F.data == "consent:no")
async def on_consent_no(cq: CallbackQuery) -> None:
    await cq.message.edit_text(
        "Без согласия я не могу сохранять ваши медицинские данные. "
        "Когда передумаете — наберите /start."
    )
    await cq.answer()


@router.message(Command("forget_me"))
async def cmd_forget(message: Message, session: AsyncSession, user: User) -> None:
    svc = UserService(session)
    await svc.forget_patient(user)
    await message.answer(
        "Все ваши медицинские данные удалены. Согласие отозвано. /start чтобы начать заново."
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено. /start — главное меню.")


@router.callback_query(F.data == "cancel")
async def cb_cancel(cq: CallbackQuery, state: FSMContext, user: User) -> None:
    await state.clear()
    await cq.message.edit_text(
        "Главное меню:",
        reply_markup=main_menu(is_doctor=(user.role == UserRole.DOCTOR)),
    )
    await cq.answer()
