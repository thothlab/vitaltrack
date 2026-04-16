from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import cancel_kb, now_or_input_kb, skip_cancel_kb
from app.bot.keyboards.patient import record_menu
from app.bot.states.labs import LabFSM
from app.db.models import User
from app.domain.schemas import LabIn
from app.services.labs import LabService
from app.utils.i18n import t
from app.utils.time import now_utc, parse_user_datetime

router = Router(name="labs")


@router.callback_query(F.data == "rec:lab")
async def start(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(LabFSM.waiting_date)
    await cq.message.edit_text(
        "Дата сдачи анализа (например 02.04 09:00 или «Сейчас»):",
        reply_markup=now_or_input_kb(),
    )
    await cq.answer()


@router.callback_query(LabFSM.waiting_date, F.data == "time:now")
async def date_now(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(drawn_at=now_utc().isoformat())
    await _ask_chol(cq.message, state)
    await cq.answer()


@router.message(LabFSM.waiting_date)
async def date_input(message: Message, state: FSMContext, user: User) -> None:
    try:
        dt = parse_user_datetime(message.text or "", user.timezone)
    except ValueError:
        await message.answer("Не понял дату.")
        return
    await state.update_data(drawn_at=dt.isoformat())
    await _ask_chol(message, state)


async def _ask_chol(target, state: FSMContext) -> None:
    await state.set_state(LabFSM.waiting_total_chol)
    await target.answer("Общий холестерин (ммоль/л) или «Пропустить»:", reply_markup=skip_cancel_kb())


def _make_step(field: str, prompt: str, next_state, terminal: bool = False):
    async def text_handler(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
        text = (message.text or "").replace(",", ".").strip()
        try:
            value = float(text) if text else None
        except ValueError:
            await message.answer("Нужно число или «Пропустить».")
            return
        await state.update_data({field: value})
        if terminal:
            await _finish(message, state, session, user)
        else:
            await state.set_state(next_state)
            await message.answer(prompt, reply_markup=skip_cancel_kb())

    async def skip_handler(cq: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
        await state.update_data({field: None})
        if terminal:
            await _finish(cq.message, state, session, user)
        else:
            await state.set_state(next_state)
            await cq.message.edit_text(prompt, reply_markup=skip_cancel_kb())
        await cq.answer()
    return text_handler, skip_handler


_chol_text, _chol_skip = _make_step("total_chol", "ЛПНП (ммоль/л) или «Пропустить»:", LabFSM.waiting_ldl)
_ldl_text, _ldl_skip = _make_step("ldl", "ЛПВП (ммоль/л) или «Пропустить»:", LabFSM.waiting_hdl)
_hdl_text, _hdl_skip = _make_step("hdl", "Триглицериды (ммоль/л) или «Пропустить»:", LabFSM.waiting_tg)
_tg_text, _tg_skip = _make_step("triglycerides", "Глюкоза натощак (ммоль/л) или «Пропустить»:", LabFSM.waiting_glucose)
_glu_text, _glu_skip = _make_step("glucose_fasting", "Инсулин натощак (µU/mL) или «Пропустить»:", LabFSM.waiting_insulin)
_ins_text, _ins_skip = _make_step("insulin_fasting", "Креатинин (µмоль/л) или «Пропустить»:", LabFSM.waiting_creatinine)
_cr_text, _cr_skip = _make_step("creatinine_umol", "", None, terminal=True)


router.message.register(_chol_text, LabFSM.waiting_total_chol)
router.callback_query.register(_chol_skip, LabFSM.waiting_total_chol, F.data == "skip")
router.message.register(_ldl_text, LabFSM.waiting_ldl)
router.callback_query.register(_ldl_skip, LabFSM.waiting_ldl, F.data == "skip")
router.message.register(_hdl_text, LabFSM.waiting_hdl)
router.callback_query.register(_hdl_skip, LabFSM.waiting_hdl, F.data == "skip")
router.message.register(_tg_text, LabFSM.waiting_tg)
router.callback_query.register(_tg_skip, LabFSM.waiting_tg, F.data == "skip")
router.message.register(_glu_text, LabFSM.waiting_glucose)
router.callback_query.register(_glu_skip, LabFSM.waiting_glucose, F.data == "skip")
router.message.register(_ins_text, LabFSM.waiting_insulin)
router.callback_query.register(_ins_skip, LabFSM.waiting_insulin, F.data == "skip")
router.message.register(_cr_text, LabFSM.waiting_creatinine)
router.callback_query.register(_cr_skip, LabFSM.waiting_creatinine, F.data == "skip")


async def _finish(target, state: FSMContext, session: AsyncSession, user: User) -> None:
    data = await state.get_data()
    payload = LabIn(
        drawn_at=datetime.fromisoformat(data["drawn_at"]),
        total_chol=data.get("total_chol"),
        ldl=data.get("ldl"),
        hdl=data.get("hdl"),
        triglycerides=data.get("triglycerides"),
        glucose_fasting=data.get("glucose_fasting"),
        insulin_fasting=data.get("insulin_fasting"),
        creatinine_umol=data.get("creatinine_umol"),
    )
    await LabService(session).add(user, payload)
    await state.clear()
    await target.answer("✅ Анализ сохранён.", reply_markup=record_menu())
