"""GI symptom logging — pain, nausea, heartburn, bloating, Bristol stool scale."""
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

from app.bot.keyboards.common import now_or_input_kb, skip_cancel_kb
from app.bot.keyboards.patient import record_menu
from app.bot.states.gi import GIFSM
from app.db.models import GIRecord, User
from app.domain.schemas import GIRecordIn
from app.repositories.gi import GIRepository
from app.utils.i18n import t
from app.utils.time import now_utc, parse_user_datetime

router = Router(name="gi")

_SCALE_LABELS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
_BRISTOL_HINTS = (
    "1 — твёрдые комки (запор)\n"
    "2 — комковатая «сосиска»\n"
    "3 — «сосиска» с трещинами\n"
    "4 — гладкая мягкая «сосиска» (норма)\n"
    "5 — мягкие кусочки\n"
    "6 — рыхлая кашица\n"
    "7 — водянистый (диарея)"
)


def _scale_kb(prefix: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=str(i), callback_data=f"{prefix}:{i}") for i in range(6)],
        [InlineKeyboardButton(text=str(i), callback_data=f"{prefix}:{i}") for i in range(6, 11)],
        [InlineKeyboardButton(text=t("skip"), callback_data=f"{prefix}:skip")],
        [InlineKeyboardButton(text=t("cancel"), callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _bristol_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=str(i), callback_data=f"gi_stool:{i}") for i in range(1, 5)],
        [InlineKeyboardButton(text=str(i), callback_data=f"gi_stool:{i}") for i in range(5, 8)],
        [InlineKeyboardButton(text="Не было", callback_data="gi_stool:skip")],
        [InlineKeyboardButton(text=t("cancel"), callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------- entry point ----------
@router.callback_query(F.data == "rec:gi")
async def start(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GIFSM.waiting_time)
    await cq.message.edit_text(t("ask_time_symptoms"), reply_markup=now_or_input_kb())
    await cq.answer()


@router.callback_query(GIFSM.waiting_time, F.data == "time:now")
async def time_now(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(occurred_at=now_utc().isoformat())
    await state.set_state(GIFSM.waiting_pain)
    await cq.message.edit_text("Боль в животе (0 — нет, 10 — невыносимая):",
                               reply_markup=_scale_kb("gi_pain"))
    await cq.answer()


@router.message(GIFSM.waiting_time)
async def time_input(message: Message, state: FSMContext, user: User) -> None:
    try:
        dt = parse_user_datetime(message.text or "", user.timezone)
    except ValueError:
        await message.answer("Не понял время. Попробуйте ещё раз.")
        return
    await state.update_data(occurred_at=dt.isoformat())
    await state.set_state(GIFSM.waiting_pain)
    await message.answer("Боль в животе (0 — нет, 10 — невыносимая):",
                         reply_markup=_scale_kb("gi_pain"))


# ---------- pain ----------
@router.callback_query(GIFSM.waiting_pain, F.data.startswith("gi_pain:"))
async def pain_chosen(cq: CallbackQuery, state: FSMContext) -> None:
    val = cq.data.split(":")[1]
    await state.update_data(pain=None if val == "skip" else int(val))
    await state.set_state(GIFSM.waiting_nausea)
    await cq.message.edit_text("Тошнота (0 — нет, 10 — сильная):",
                               reply_markup=_scale_kb("gi_nausea"))
    await cq.answer()


# ---------- nausea ----------
@router.callback_query(GIFSM.waiting_nausea, F.data.startswith("gi_nausea:"))
async def nausea_chosen(cq: CallbackQuery, state: FSMContext) -> None:
    val = cq.data.split(":")[1]
    await state.update_data(nausea=None if val == "skip" else int(val))
    await state.set_state(GIFSM.waiting_heartburn)
    await cq.message.edit_text("Изжога (0 — нет, 10 — сильная):",
                               reply_markup=_scale_kb("gi_heartburn"))
    await cq.answer()


# ---------- heartburn ----------
@router.callback_query(GIFSM.waiting_heartburn, F.data.startswith("gi_heartburn:"))
async def heartburn_chosen(cq: CallbackQuery, state: FSMContext) -> None:
    val = cq.data.split(":")[1]
    await state.update_data(heartburn=None if val == "skip" else int(val))
    await state.set_state(GIFSM.waiting_bloating)
    await cq.message.edit_text("Вздутие / газы (0 — нет, 10 — сильное):",
                               reply_markup=_scale_kb("gi_bloating"))
    await cq.answer()


# ---------- bloating ----------
@router.callback_query(GIFSM.waiting_bloating, F.data.startswith("gi_bloating:"))
async def bloating_chosen(cq: CallbackQuery, state: FSMContext) -> None:
    val = cq.data.split(":")[1]
    await state.update_data(bloating=None if val == "skip" else int(val))
    await state.set_state(GIFSM.waiting_stool)
    await cq.message.edit_text(
        f"Стул по Бристольской шкале:\n\n{_BRISTOL_HINTS}",
        reply_markup=_bristol_kb(),
    )
    await cq.answer()


# ---------- stool ----------
@router.callback_query(GIFSM.waiting_stool, F.data.startswith("gi_stool:"))
async def stool_chosen(cq: CallbackQuery, state: FSMContext) -> None:
    val = cq.data.split(":")[1]
    await state.update_data(stool_bristol=None if val == "skip" else int(val))
    await state.set_state(GIFSM.waiting_notes)
    await cq.message.edit_text("Добавьте заметку (или нажмите «Пропустить»):", reply_markup=skip_cancel_kb())
    await cq.answer()


# ---------- notes ----------
@router.callback_query(GIFSM.waiting_notes, F.data == "skip")
async def notes_skip(cq: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    await _persist(state, session, user)
    await state.clear()
    await cq.message.edit_text("✅ Запись ЖКТ сохранена.", reply_markup=record_menu())
    await cq.answer()


@router.message(GIFSM.waiting_notes)
async def notes_input(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    await state.update_data(note=(message.text or "").strip() or None)
    await _persist(state, session, user)
    await state.clear()
    await message.answer("✅ Запись ЖКТ сохранена.", reply_markup=record_menu())


async def _persist(state: FSMContext, session: AsyncSession, user: User) -> None:
    data = await state.get_data()
    payload = GIRecordIn(
        occurred_at=datetime.fromisoformat(data["occurred_at"]),
        pain=data.get("pain"),
        nausea=data.get("nausea"),
        heartburn=data.get("heartburn"),
        bloating=data.get("bloating"),
        stool_bristol=data.get("stool_bristol"),
        note=data.get("note"),
    )
    rec = GIRecord(
        user_id=user.id,
        occurred_at=payload.occurred_at,
        pain=payload.pain,
        nausea=payload.nausea,
        heartburn=payload.heartburn,
        bloating=payload.bloating,
        stool_bristol=payload.stool_bristol,
        note=payload.note,
    )
    await GIRepository(session).add(rec)
