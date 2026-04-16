from __future__ import annotations

import uuid

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import cancel_kb, now_or_input_kb, skip_cancel_kb, yes_no_kb
from app.bot.keyboards.patient import record_menu
from app.bot.states.pressure import PressureFSM
from app.db.models import User
from app.domain.schemas import PressureIn
from app.services.alerts import AlertService
from app.services.pressure import PressureService
from app.utils.i18n import t
from app.utils.time import now_utc, parse_user_datetime

router = Router(name="pressure")


@router.callback_query(F.data == "rec:pressure")
async def start_flow(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PressureFSM.waiting_time)
    await state.update_data(session_uuid=str(uuid.uuid4()))
    await cq.message.edit_text(t("ask_time"), reply_markup=now_or_input_kb())
    await cq.answer()


@router.callback_query(PressureFSM.waiting_time, F.data == "time:now")
async def time_now(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(measured_at=now_utc().isoformat())
    await state.set_state(PressureFSM.waiting_systolic)
    await cq.message.edit_text("Введите САД (верхнее), число:", reply_markup=cancel_kb())
    await cq.answer()


@router.message(PressureFSM.waiting_time)
async def time_input(message: Message, state: FSMContext, user: User) -> None:
    try:
        dt = parse_user_datetime(message.text or "", user.timezone)
    except ValueError:
        await message.answer("Не понял время. Попробуйте: 21:30 · вчера 09:00 · 02.04 08:15")
        return
    await state.update_data(measured_at=dt.isoformat())
    await state.set_state(PressureFSM.waiting_systolic)
    await message.answer("Введите САД (верхнее), число:", reply_markup=cancel_kb())


@router.message(PressureFSM.waiting_systolic)
async def sys_input(message: Message, state: FSMContext) -> None:
    if not (message.text or "").strip().isdigit():
        await message.answer("Нужно число, например 135")
        return
    await state.update_data(systolic=int(message.text))
    await state.set_state(PressureFSM.waiting_diastolic)
    await message.answer("Введите ДАД (нижнее), число:", reply_markup=cancel_kb())


@router.message(PressureFSM.waiting_diastolic)
async def dia_input(message: Message, state: FSMContext) -> None:
    if not (message.text or "").strip().isdigit():
        await message.answer("Нужно число, например 85")
        return
    await state.update_data(diastolic=int(message.text))
    await state.set_state(PressureFSM.waiting_pulse)
    await message.answer("Введите пульс (или «Пропустить»):", reply_markup=skip_cancel_kb())


@router.callback_query(PressureFSM.waiting_pulse, F.data == "skip")
async def skip_pulse(cq: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    await _persist_and_ask_more(cq.message, state, session, user)
    await cq.answer()


@router.message(PressureFSM.waiting_pulse)
async def pulse_input(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    text = (message.text or "").strip()
    pulse = None
    if text:
        if not text.isdigit():
            await message.answer("Нужно число или «Пропустить».")
            return
        pulse = int(text)
    await state.update_data(pulse=pulse)
    await _persist_and_ask_more(message, state, session, user)


async def _persist_and_ask_more(target, state: FSMContext, session: AsyncSession, user: User) -> None:
    data = await state.get_data()
    from datetime import datetime
    payload = PressureIn(
        measured_at=datetime.fromisoformat(data["measured_at"]),
        systolic=int(data["systolic"]),
        diastolic=int(data["diastolic"]),
        pulse=data.get("pulse"),
        session_uuid=data.get("session_uuid"),
    )
    rec = await PressureService(session).add(user, payload)
    await session.flush()
    alert = await AlertService(session).evaluate_pressure(user, rec)
    await state.set_state(PressureFSM.waiting_more)
    msg = f"✅ Сохранено: {payload.systolic}/{payload.diastolic}"
    if payload.pulse is not None:
        msg += f" · ЧСС {payload.pulse}"
    if alert:
        msg += f"\n⚠️ {alert['summary']}"
    await target.answer(msg + "\nЕщё одно измерение?", reply_markup=yes_no_kb("more"))


@router.callback_query(PressureFSM.waiting_more, F.data == "more:yes")
async def more_yes(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PressureFSM.waiting_systolic)
    await cq.message.edit_text("Введите САД (верхнее):", reply_markup=cancel_kb())
    await cq.answer()


@router.callback_query(PressureFSM.waiting_more, F.data == "more:no")
async def more_no(cq: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cq.message.edit_text("Готово.", reply_markup=record_menu())
    await cq.answer()
