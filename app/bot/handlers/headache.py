"""Headache / migraine diary — ICHD-3 inspired, like Migrebot."""
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
from app.bot.states.headache import HeadacheFSM
from app.db.models import HeadacheAttack, User
from app.domain.enums import HeadacheCharacter, HeadacheLocation
from app.domain.schemas import HeadacheAttackIn
from app.repositories.headache import HeadacheRepository
from app.utils.i18n import t
from app.utils.time import now_utc, parse_user_datetime

router = Router(name="headache")

_LOCATION_LABELS = {
    HeadacheLocation.LEFT: "Левая сторона",
    HeadacheLocation.RIGHT: "Правая сторона",
    HeadacheLocation.BILATERAL: "Обе стороны",
    HeadacheLocation.WHOLE: "Вся голова",
}

_CHARACTER_LABELS = {
    HeadacheCharacter.PULSATING: "🫀 Пульсирующая",
    HeadacheCharacter.PRESSING: "🏋️ Давящая / сжимающая",
    HeadacheCharacter.STABBING: "🔪 Колющая",
    HeadacheCharacter.OTHER: "Другая",
}

_ASSOC_ITEMS = [
    ("nausea", "Тошнота"),
    ("vomiting", "Рвота"),
    ("photophobia", "Светобоязнь"),
    ("phonophobia", "Звукобоязнь"),
    ("aura", "Аура (зрительные / чувствительные явления)"),
]

_TRIGGER_OPTIONS = [
    ("stress", "😰 Стресс"),
    ("sleep_poor", "😴 Плохой сон"),
    ("weather", "🌦 Погода"),
    ("alcohol", "🍷 Алкоголь"),
    ("hormonal", "🔬 Гормональные (менструация и др.)"),
    ("bright_light", "💡 Яркий свет / экран"),
    ("food", "🍔 Еда / голод"),
    ("other", "Другое"),
]

_DISABILITY_LABELS = [
    "0 — нет ограничений",
    "1 — лёгкие (могу работать)",
    "2 — умеренные (работаю с трудом)",
    "3 — тяжёлые (не могу работать)",
]


def _intensity_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=str(i), callback_data=f"ha_int:{i}") for i in range(1, 6)],
        [InlineKeyboardButton(text=str(i), callback_data=f"ha_int:{i}") for i in range(6, 11)],
        [InlineKeyboardButton(text=t("cancel"), callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _location_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"ha_loc:{loc.value}")]
        for loc, label in _LOCATION_LABELS.items()
    ]
    rows.append([InlineKeyboardButton(text=t("skip"), callback_data="ha_loc:skip")])
    rows.append([InlineKeyboardButton(text=t("cancel"), callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _character_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"ha_char:{ch.value}")]
        for ch, label in _CHARACTER_LABELS.items()
    ]
    rows.append([InlineKeyboardButton(text=t("skip"), callback_data="ha_char:skip")])
    rows.append([InlineKeyboardButton(text=t("cancel"), callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _assoc_kb(selected: set[str]) -> InlineKeyboardMarkup:
    rows = []
    for key, label in _ASSOC_ITEMS:
        mark = "✅ " if key in selected else "☐ "
        rows.append([InlineKeyboardButton(text=mark + label, callback_data=f"ha_assoc:{key}")])
    rows.append([InlineKeyboardButton(text="✔ Готово", callback_data="ha_assoc:done")])
    rows.append([InlineKeyboardButton(text=t("cancel"), callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _triggers_kb(selected: set[str]) -> InlineKeyboardMarkup:
    rows = []
    for key, label in _TRIGGER_OPTIONS:
        mark = "✅ " if key in selected else "☐ "
        rows.append([InlineKeyboardButton(text=mark + label, callback_data=f"ha_trig:{key}")])
    rows.append([InlineKeyboardButton(text="☐ Триггеров нет", callback_data="ha_trig:none")])
    rows.append([InlineKeyboardButton(text="✔ Готово", callback_data="ha_trig:done")])
    rows.append([InlineKeyboardButton(text=t("cancel"), callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _disability_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"ha_dis:{i}")]
        for i, label in enumerate(_DISABILITY_LABELS)
    ]
    rows.append([InlineKeyboardButton(text=t("skip"), callback_data="ha_dis:skip")])
    rows.append([InlineKeyboardButton(text=t("cancel"), callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------- entry point ----------
@router.callback_query(F.data == "rec:headache")
async def start(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(HeadacheFSM.waiting_time)
    await cq.message.edit_text(t("ask_time"), reply_markup=now_or_input_kb())
    await cq.answer()


@router.callback_query(HeadacheFSM.waiting_time, F.data == "time:now")
async def time_now(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(started_at=now_utc().isoformat())
    await _ask_intensity(cq.message.edit_text, state)
    await cq.answer()


@router.message(HeadacheFSM.waiting_time)
async def time_input(message: Message, state: FSMContext, user: User) -> None:
    try:
        dt = parse_user_datetime(message.text or "", user.timezone)
    except ValueError:
        await message.answer("Не понял время. Попробуйте ещё раз.")
        return
    await state.update_data(started_at=dt.isoformat())
    await _ask_intensity(message.answer, state)


async def _ask_intensity(send_fn, state: FSMContext) -> None:
    await state.set_state(HeadacheFSM.waiting_intensity)
    await send_fn(
        "Интенсивность боли по шкале ВАШ (1 — почти нет, 10 — невыносимо):",
        reply_markup=_intensity_kb(),
    )


# ---------- intensity ----------
@router.callback_query(HeadacheFSM.waiting_intensity, F.data.startswith("ha_int:"))
async def intensity_chosen(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(intensity=int(cq.data.split(":")[1]))
    await state.set_state(HeadacheFSM.waiting_location)
    await cq.message.edit_text("Локализация боли:", reply_markup=_location_kb())
    await cq.answer()


# ---------- location ----------
@router.callback_query(HeadacheFSM.waiting_location, F.data.startswith("ha_loc:"))
async def location_chosen(cq: CallbackQuery, state: FSMContext) -> None:
    val = cq.data.split(":")[1]
    await state.update_data(location=None if val == "skip" else val)
    await state.set_state(HeadacheFSM.waiting_character)
    await cq.message.edit_text("Характер боли:", reply_markup=_character_kb())
    await cq.answer()


# ---------- character ----------
@router.callback_query(HeadacheFSM.waiting_character, F.data.startswith("ha_char:"))
async def character_chosen(cq: CallbackQuery, state: FSMContext) -> None:
    val = cq.data.split(":")[1]
    await state.update_data(character=None if val == "skip" else val)
    await state.update_data(assoc_selected=[])
    await state.set_state(HeadacheFSM.waiting_assoc)
    await cq.message.edit_text(
        "Сопутствующие симптомы (выберите все подходящие):",
        reply_markup=_assoc_kb(set()),
    )
    await cq.answer()


# ---------- associated symptoms multi-select ----------
@router.callback_query(HeadacheFSM.waiting_assoc, F.data.startswith("ha_assoc:"))
async def assoc_toggle(cq: CallbackQuery, state: FSMContext) -> None:
    val = cq.data.split(":")[1]
    data = await state.get_data()
    selected: set[str] = set(data.get("assoc_selected") or [])

    if val == "done":
        await state.set_state(HeadacheFSM.waiting_triggers)
        await state.update_data(triggers_selected=[])
        await cq.message.edit_text(
            "Триггеры (выберите все подходящие):",
            reply_markup=_triggers_kb(set()),
        )
    else:
        if val in selected:
            selected.discard(val)
        else:
            selected.add(val)
        await state.update_data(assoc_selected=list(selected))
        await cq.message.edit_reply_markup(reply_markup=_assoc_kb(selected))
    await cq.answer()


# ---------- triggers multi-select ----------
@router.callback_query(HeadacheFSM.waiting_triggers, F.data.startswith("ha_trig:"))
async def trigger_toggle(cq: CallbackQuery, state: FSMContext) -> None:
    val = cq.data.split(":")[1]
    data = await state.get_data()
    selected: set[str] = set(data.get("triggers_selected") or [])

    if val == "done":
        await state.set_state(HeadacheFSM.waiting_disability)
        await cq.message.edit_text("Нетрудоспособность:", reply_markup=_disability_kb())
    elif val == "none":
        await state.update_data(triggers_selected=[])
        await state.set_state(HeadacheFSM.waiting_disability)
        await cq.message.edit_text("Нетрудоспособность:", reply_markup=_disability_kb())
    else:
        if val in selected:
            selected.discard(val)
        else:
            selected.add(val)
        await state.update_data(triggers_selected=list(selected))
        await cq.message.edit_reply_markup(reply_markup=_triggers_kb(selected))
    await cq.answer()


# ---------- disability ----------
@router.callback_query(HeadacheFSM.waiting_disability, F.data.startswith("ha_dis:"))
async def disability_chosen(cq: CallbackQuery, state: FSMContext) -> None:
    val = cq.data.split(":")[1]
    await state.update_data(disability=None if val == "skip" else int(val))
    await state.set_state(HeadacheFSM.waiting_duration)
    await cq.message.edit_text(
        "Длительность приступа (в часах, например «4» или «1.5»), или «Пропустить»:",
        reply_markup=skip_cancel_kb(),
    )
    await cq.answer()


# ---------- duration ----------
@router.callback_query(HeadacheFSM.waiting_duration, F.data == "skip")
async def duration_skip(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(duration_hours=None)
    await state.set_state(HeadacheFSM.waiting_notes)
    await cq.message.edit_text("Заметки (или «Пропустить»):", reply_markup=skip_cancel_kb())
    await cq.answer()


@router.message(HeadacheFSM.waiting_duration)
async def duration_input(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip().replace(",", ".")
    try:
        hours = float(text)
        if hours <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите число часов, например «4» или «1.5».")
        return
    await state.update_data(duration_hours=hours)
    await state.set_state(HeadacheFSM.waiting_notes)
    await message.answer("Заметки (или «Пропустить»):", reply_markup=skip_cancel_kb())


# ---------- notes ----------
@router.callback_query(HeadacheFSM.waiting_notes, F.data == "skip")
async def notes_skip(cq: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    await _persist(state, session, user)
    await state.clear()
    await cq.message.edit_text("✅ Приступ головной боли записан.", reply_markup=record_menu())
    await cq.answer()


@router.message(HeadacheFSM.waiting_notes)
async def notes_input(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    await state.update_data(note=(message.text or "").strip() or None)
    await _persist(state, session, user)
    await state.clear()
    await message.answer("✅ Приступ головной боли записан.", reply_markup=record_menu())


async def _persist(state: FSMContext, session: AsyncSession, user: User) -> None:
    data = await state.get_data()
    assoc: set[str] = set(data.get("assoc_selected") or [])
    triggers: list[str] = data.get("triggers_selected") or []

    loc_val = data.get("location")
    char_val = data.get("character")

    payload = HeadacheAttackIn(
        started_at=datetime.fromisoformat(data["started_at"]),
        intensity=data["intensity"],
        location=HeadacheLocation(loc_val) if loc_val else None,
        character=HeadacheCharacter(char_val) if char_val else None,
        duration_hours=data.get("duration_hours"),
        nausea="nausea" in assoc,
        vomiting="vomiting" in assoc,
        photophobia="photophobia" in assoc,
        phonophobia="phonophobia" in assoc,
        aura="aura" in assoc,
        triggers=triggers,
        disability=data.get("disability"),
        note=data.get("note"),
    )
    attack = HeadacheAttack(
        user_id=user.id,
        started_at=payload.started_at,
        intensity=payload.intensity,
        location=payload.location,
        character=payload.character,
        duration_hours=payload.duration_hours,
        nausea=payload.nausea,
        vomiting=payload.vomiting,
        photophobia=payload.photophobia,
        phonophobia=payload.phonophobia,
        aura=payload.aura,
        triggers=payload.triggers,
        disability=payload.disability,
        note=payload.note,
    )
    await HeadacheRepository(session).add(attack)
