from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
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


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    await state.clear()
    if user.consent_at is None:
        await message.answer(t("consent_request"), reply_markup=consent_kb())
        return
    await message.answer(
        f"Здравствуйте, {user.full_name or ''}! Я VitalTrack — ваш медицинский "
        f"дневник. Выберите действие:",
        reply_markup=main_menu(is_doctor=(user.role == UserRole.DOCTOR)),
    )


@router.callback_query(F.data == "consent:yes")
async def on_consent_yes(cq: CallbackQuery, session: AsyncSession, user: User) -> None:
    await UserService(session).grant_consent(user)
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
