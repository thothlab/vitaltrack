from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import cancel_kb, now_or_input_kb
from app.bot.keyboards.patient import record_menu
from app.bot.states.glucose import GlucoseFSM
from app.db.models import User
from app.domain.enums import GlucoseContext
from app.domain.schemas import GlucoseIn
from app.services.alerts import AlertService
from app.services.glucose import GlucoseService
from app.utils.i18n import t
from app.utils.time import now_utc, parse_user_datetime

router = Router(name="glucose")


def _context_kb() -> InlineKeyboardMarkup:
    labels = {
        GlucoseContext.FASTING: "Натощак",
        GlucoseContext.BEFORE_MEAL: "До еды",
        GlucoseContext.POST_MEAL: "После еды",
        GlucoseContext.BEDTIME: "Перед сном",
        GlucoseContext.RANDOM: "Случайно",
    }
    rows = [
        [InlineKeyboardButton(text=labels[c], callback_data=f"gctx:{c.value}")]
        for c in GlucoseContext
    ]
    rows.append([InlineKeyboardButton(text=t("cancel"), callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "rec:glucose")
async def start_flow(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GlucoseFSM.waiting_time)
    await cq.message.edit_text(t("ask_time"), reply_markup=now_or_input_kb())
    await cq.answer()


@router.callback_query(GlucoseFSM.waiting_time, F.data == "time:now")
async def time_now(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(measured_at=now_utc().isoformat())
    await state.set_state(GlucoseFSM.waiting_value)
    await cq.message.edit_text("Введите значение глюкозы, ммоль/л (например 5.6):",
                               reply_markup=cancel_kb())
    await cq.answer()


@router.message(GlucoseFSM.waiting_time)
async def time_input(message: Message, state: FSMContext, user: User) -> None:
    try:
        dt = parse_user_datetime(message.text or "", user.timezone)
    except ValueError:
        await message.answer("Не понял время. Попробуйте: 21:30 · вчера 09:00")
        return
    await state.update_data(measured_at=dt.isoformat())
    await state.set_state(GlucoseFSM.waiting_value)
    await message.answer("Введите значение глюкозы, ммоль/л:", reply_markup=cancel_kb())


@router.message(GlucoseFSM.waiting_value)
async def value_input(message: Message, state: FSMContext) -> None:
    text = (message.text or "").replace(",", ".").strip()
    try:
        value = float(text)
    except ValueError:
        await message.answer("Нужно число, например 5.6")
        return
    if not (0 < value < 60):
        await message.answer("Значение вне диапазона. Введите реальное число.")
        return
    await state.update_data(value_mmol=value)
    await state.set_state(GlucoseFSM.waiting_context)
    await message.answer("Контекст измерения:", reply_markup=_context_kb())


@router.callback_query(GlucoseFSM.waiting_context, F.data.startswith("gctx:"))
async def context_chosen(cq: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    ctx_value = cq.data.split(":", 1)[1]
    data = await state.get_data()
    payload = GlucoseIn(
        measured_at=datetime.fromisoformat(data["measured_at"]),
        value_mmol=float(data["value_mmol"]),
        context=GlucoseContext(ctx_value),
    )
    rec = await GlucoseService(session).add(user, payload)
    await session.flush()
    alert = await AlertService(session).evaluate_glucose(user, rec)
    await state.clear()
    msg = f"✅ Сохранено: {payload.value_mmol} ммоль/л ({ctx_value})"
    if alert:
        msg += f"\n⚠️ {alert['summary']}"
    await cq.message.edit_text(msg, reply_markup=record_menu())
    await cq.answer()
