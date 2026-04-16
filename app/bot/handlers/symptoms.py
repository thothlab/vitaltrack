from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import cancel_kb, now_or_input_kb, skip_cancel_kb
from app.bot.keyboards.patient import record_menu
from app.bot.states.symptoms import SymptomFSM
from app.db.models import User
from app.domain.enums import WellbeingGrade
from app.domain.schemas import SymptomIn
from app.services.symptoms import SymptomService
from app.utils.i18n import t
from app.utils.time import now_utc, parse_user_datetime

router = Router(name="symptoms")


def _wellbeing_kb() -> InlineKeyboardMarkup:
    labels = {
        WellbeingGrade.GREAT: "Отлично",
        WellbeingGrade.GOOD: "Хорошо",
        WellbeingGrade.OK: "Нормально",
        WellbeingGrade.POOR: "Плохо",
        WellbeingGrade.BAD: "Очень плохо",
    }
    rows = [
        [InlineKeyboardButton(text=labels[g], callback_data=f"wb:{g.value}")]
        for g in WellbeingGrade
    ]
    rows.append([InlineKeyboardButton(text=t("cancel"), callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "rec:symptoms")
async def start(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SymptomFSM.waiting_time)
    await cq.message.edit_text(t("ask_time"), reply_markup=now_or_input_kb())
    await cq.answer()


@router.callback_query(SymptomFSM.waiting_time, F.data == "time:now")
async def time_now(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(occurred_at=now_utc().isoformat())
    await state.set_state(SymptomFSM.waiting_wellbeing)
    await cq.message.edit_text("Самочувствие:", reply_markup=_wellbeing_kb())
    await cq.answer()


@router.message(SymptomFSM.waiting_time)
async def time_input(message: Message, state: FSMContext, user: User) -> None:
    try:
        dt = parse_user_datetime(message.text or "", user.timezone)
    except ValueError:
        await message.answer("Не понял время.")
        return
    await state.update_data(occurred_at=dt.isoformat())
    await state.set_state(SymptomFSM.waiting_wellbeing)
    await message.answer("Самочувствие:", reply_markup=_wellbeing_kb())


@router.callback_query(SymptomFSM.waiting_wellbeing, F.data.startswith("wb:"))
async def wellbeing_chosen(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(wellbeing=cq.data.split(":")[1])
    await state.set_state(SymptomFSM.waiting_symptoms)
    await cq.message.edit_text(
        "Перечислите симптомы через запятую (или «Пропустить»):",
        reply_markup=skip_cancel_kb(),
    )
    await cq.answer()


@router.callback_query(SymptomFSM.waiting_symptoms, F.data == "skip")
async def skip_symptoms(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(symptoms=[])
    await state.set_state(SymptomFSM.waiting_intensity)
    await cq.message.edit_text("Интенсивность 1-10 (или «Пропустить»):",
                               reply_markup=skip_cancel_kb())
    await cq.answer()


@router.message(SymptomFSM.waiting_symptoms)
async def symptoms_input(message: Message, state: FSMContext) -> None:
    items = [s.strip() for s in (message.text or "").split(",") if s.strip()]
    await state.update_data(symptoms=items)
    await state.set_state(SymptomFSM.waiting_intensity)
    await message.answer("Интенсивность 1-10 (или «Пропустить»):", reply_markup=skip_cancel_kb())


@router.callback_query(SymptomFSM.waiting_intensity, F.data == "skip")
async def skip_intensity(cq: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    await _persist(state, session, user)
    await cq.message.edit_text("✅ Сохранено.", reply_markup=record_menu())
    await state.clear()
    await cq.answer()


@router.message(SymptomFSM.waiting_intensity)
async def intensity_input(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    text = (message.text or "").strip()
    if not text.isdigit() or not (1 <= int(text) <= 10):
        await message.answer("Число от 1 до 10.")
        return
    await state.update_data(intensity=int(text))
    await _persist(state, session, user)
    await state.clear()
    await message.answer("✅ Сохранено.", reply_markup=record_menu())


async def _persist(state: FSMContext, session: AsyncSession, user: User) -> None:
    data = await state.get_data()
    payload = SymptomIn(
        occurred_at=datetime.fromisoformat(data["occurred_at"]),
        wellbeing=WellbeingGrade(data["wellbeing"]),
        symptoms=data.get("symptoms") or [],
        intensity=data.get("intensity"),
    )
    await SymptomService(session).add(user, payload)
