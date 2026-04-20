from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import cancel_kb
from app.bot.keyboards.patient import settings_menu
from app.bot.states.doctor import DoctorLinkFSM
from app.db.models import User
from app.domain.enums import UserRole
from app.repositories.users import UserRepository
from app.services.users import UserService

router = Router(name="settings")


@router.callback_query(F.data == "set:tz")
async def ask_tz(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state("tz_input")
    await cq.message.edit_text(
        "Введите название часового пояса в формате IANA, например Europe/Moscow:",
        reply_markup=cancel_kb(),
    )
    await cq.answer()


@router.message(F.text, lambda m: m.text and "/" in (m.text or ""))
async def maybe_tz(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    cur = await state.get_state()
    if cur != "tz_input":
        return
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        ZoneInfo(message.text.strip())
    except ZoneInfoNotFoundError:
        await message.answer("Неизвестный часовой пояс.")
        return
    user.timezone = message.text.strip()
    await state.clear()
    await message.answer(f"Часовой пояс установлен: {user.timezone}",
                         reply_markup=settings_menu())


@router.callback_query(F.data == "set:doctor")
async def ask_doctor(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DoctorLinkFSM.waiting_patient_id)
    await cq.message.edit_text(
        "Введите Telegram ID вашего врача (число):", reply_markup=cancel_kb()
    )
    await cq.answer()


@router.message(DoctorLinkFSM.waiting_patient_id)
async def link_doctor(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Нужно число.")
        return
    repo = UserRepository(session)
    doctor = await repo.by_telegram(int(text))
    if doctor is None or doctor.role != UserRole.DOCTOR:
        await message.answer("Этот пользователь не зарегистрирован как врач.")
        return
    await UserService(session).attach_patient_to_doctor(user, doctor)
    await state.clear()
    await message.answer(
        f"Врач {doctor.full_name or doctor.telegram_id} привязан.",
        reply_markup=settings_menu(),
    )


@router.callback_query(F.data == "set:forget")
async def confirm_forget(cq: CallbackQuery) -> None:
    await cq.message.edit_text(
        "Удалить ВСЕ ваши данные и отозвать согласие? Это необратимо.\n"
        "Команда: /forget_me",
        reply_markup=settings_menu(),
    )
    await cq.answer()


# `set:profile` is handled by app.bot.handlers.profile (registered earlier).
