"""Patient profile wizard.

Owns `set:profile` (entry from settings) and all `prof:*` callbacks.
Profile fields live on `User`: sex, birth_date, height_cm, weight_kg,
is_smoker, has_diabetes. The wizard either edits a single field or walks
the whole sequence; both flows return to the summary screen.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import cancel_kb, skip_cancel_kb
from app.bot.keyboards.patient import profile_menu, settings_menu
from app.bot.states.profile import ProfileFieldFSM, ProfileWizardFSM
from app.db.models import User
from app.domain.enums import Sex
from app.services.users import UserService

router = Router(name="profile")


# --------------------------------------------------------------- formatting
def _fmt(user: User) -> str:
    def line(label: str, value: object, suffix: str = "") -> str:
        if value in (None, ""):
            return f"  • {label}: <i>не задано</i>"
        return f"  • {label}: <b>{value}{suffix}</b>"

    sex_ru = {Sex.MALE: "мужской", Sex.FEMALE: "женский"}.get(user.sex, None)
    smoker = {True: "да", False: "нет"}.get(user.is_smoker, None)
    diabetes = {True: "да", False: "нет"}.get(user.has_diabetes, None)
    age = None
    if user.birth_date:
        today = date.today()
        age = today.year - user.birth_date.year - (
            (today.month, today.day) < (user.birth_date.month, user.birth_date.day)
        )

    rows = [
        "👤 <b>Профиль</b>",
        line("Пол", sex_ru),
        line(
            "Дата рождения",
            user.birth_date.strftime("%d.%m.%Y") if user.birth_date else None,
            f" (возраст {age})" if age is not None else "",
        ),
        line("Рост", user.height_cm, " см" if user.height_cm else ""),
        line("Вес", user.weight_kg, " кг" if user.weight_kg else ""),
        line("Курение", smoker),
        line("Диабет 2 типа", diabetes),
        "",
        "Профиль используется в калькуляторах (SCORE2, BMI, GFR) "
        "для подстановки значений по умолчанию.",
    ]
    return "\n".join(rows)


async def _show_summary(target: Message, user: User) -> None:
    await target.edit_text(_fmt(user), reply_markup=profile_menu())


# ---------------------------------------------------- shared input parsers
def _sex_kb(prefix: str, with_skip: bool = False) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text="Мужской", callback_data=f"{prefix}:male"),
        InlineKeyboardButton(text="Женский", callback_data=f"{prefix}:female"),
    ]]
    if with_skip:
        rows.append([InlineKeyboardButton(text="Пропустить", callback_data=f"{prefix}:skip")])
    rows.append([InlineKeyboardButton(text="✖ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _yes_no_skip_kb(prefix: str, with_skip: bool = True) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text="Да", callback_data=f"{prefix}:yes"),
        InlineKeyboardButton(text="Нет", callback_data=f"{prefix}:no"),
    ]]
    if with_skip:
        rows.append([InlineKeyboardButton(text="Пропустить", callback_data=f"{prefix}:skip")])
    rows.append([InlineKeyboardButton(text="✖ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _parse_birth(text: str) -> Optional[date]:
    text = text.strip()
    for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            d = datetime.strptime(text, fmt).date()
        except ValueError:
            continue
        today = date.today()
        if d > today or d.year < 1900:
            return None
        return d
    return None


def _parse_positive(text: str, lo: float, hi: float) -> Optional[float]:
    try:
        v = float(text.strip().replace(",", "."))
    except ValueError:
        return None
    return v if lo <= v <= hi else None


# ----------------------------------------------------- summary entry-point
@router.callback_query(F.data == "set:profile")
async def show_profile(cq: CallbackQuery, state: FSMContext, user: User) -> None:
    await state.clear()
    await _show_summary(cq.message, user)
    await cq.answer()


# =============================================================== SINGLE-FIELD
# Boolean / enum fields can be set in one tap → no FSM needed.
@router.callback_query(F.data == "prof:edit:sex")
async def edit_sex(cq: CallbackQuery) -> None:
    await cq.message.edit_text("Пол:", reply_markup=_sex_kb("prof:set:sex"))
    await cq.answer()


@router.callback_query(F.data.startswith("prof:set:sex:"))
async def set_sex(cq: CallbackQuery, session: AsyncSession, user: User) -> None:
    val = cq.data.split(":")[3]
    if val == "skip":
        await UserService(session).update_profile(user, sex=None)
    else:
        await UserService(session).update_profile(user, sex=Sex(val))
    await _show_summary(cq.message, user)
    await cq.answer("Сохранено")


@router.callback_query(F.data == "prof:edit:smoker")
async def edit_smoker(cq: CallbackQuery) -> None:
    await cq.message.edit_text("Курите?", reply_markup=_yes_no_skip_kb("prof:set:smoker"))
    await cq.answer()


@router.callback_query(F.data.startswith("prof:set:smoker:"))
async def set_smoker(cq: CallbackQuery, session: AsyncSession, user: User) -> None:
    val = cq.data.split(":")[3]
    mapping = {"yes": True, "no": False, "skip": None}
    await UserService(session).update_profile(user, is_smoker=mapping[val])
    await _show_summary(cq.message, user)
    await cq.answer("Сохранено")


@router.callback_query(F.data == "prof:edit:diabetes")
async def edit_diabetes(cq: CallbackQuery) -> None:
    await cq.message.edit_text(
        "Диабет 2 типа?", reply_markup=_yes_no_skip_kb("prof:set:diabetes")
    )
    await cq.answer()


@router.callback_query(F.data.startswith("prof:set:diabetes:"))
async def set_diabetes(cq: CallbackQuery, session: AsyncSession, user: User) -> None:
    val = cq.data.split(":")[3]
    mapping = {"yes": True, "no": False, "skip": None}
    await UserService(session).update_profile(user, has_diabetes=mapping[val])
    await _show_summary(cq.message, user)
    await cq.answer("Сохранено")


# Free-text fields: short FSM (one state per field).
@router.callback_query(F.data == "prof:edit:birth")
async def edit_birth(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProfileFieldFSM.waiting_birth)
    await cq.message.edit_text(
        "Дата рождения в формате <b>ДД.ММ.ГГГГ</b> (например, 14.05.1980):",
        reply_markup=skip_cancel_kb(),
    )
    await cq.answer()


@router.message(ProfileFieldFSM.waiting_birth)
async def on_birth(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    parsed = _parse_birth(message.text or "")
    if parsed is None:
        await message.answer("Не понял дату. Формат: ДД.ММ.ГГГГ")
        return
    await UserService(session).update_profile(user, birth_date=parsed)
    await state.clear()
    await message.answer(_fmt(user), reply_markup=profile_menu())


@router.callback_query(F.data == "prof:edit:height")
async def edit_height(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProfileFieldFSM.waiting_height)
    await cq.message.edit_text("Рост в см (например, 178):", reply_markup=skip_cancel_kb())
    await cq.answer()


@router.message(ProfileFieldFSM.waiting_height)
async def on_height(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    h = _parse_positive(message.text or "", lo=80, hi=260)
    if h is None:
        await message.answer("Нужно число от 80 до 260.")
        return
    await UserService(session).update_profile(user, height_cm=h)
    await state.clear()
    await message.answer(_fmt(user), reply_markup=profile_menu())


@router.callback_query(F.data == "prof:edit:weight")
async def edit_weight(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProfileFieldFSM.waiting_weight)
    await cq.message.edit_text("Вес в кг (например, 72.5):", reply_markup=skip_cancel_kb())
    await cq.answer()


@router.message(ProfileFieldFSM.waiting_weight)
async def on_weight(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    w = _parse_positive(message.text or "", lo=20, hi=400)
    if w is None:
        await message.answer("Нужно число от 20 до 400.")
        return
    await UserService(session).update_profile(user, weight_kg=w)
    await state.clear()
    await message.answer(_fmt(user), reply_markup=profile_menu())


# ---------------- "skip" inside per-field edits clears the field
@router.callback_query(ProfileFieldFSM.waiting_birth, F.data == "skip")
async def skip_birth(cq: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    await UserService(session).update_profile(user, birth_date=None)
    await state.clear()
    await _show_summary(cq.message, user)
    await cq.answer("Очищено")


@router.callback_query(ProfileFieldFSM.waiting_height, F.data == "skip")
async def skip_height(cq: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    await UserService(session).update_profile(user, height_cm=None)
    await state.clear()
    await _show_summary(cq.message, user)
    await cq.answer("Очищено")


@router.callback_query(ProfileFieldFSM.waiting_weight, F.data == "skip")
async def skip_weight(cq: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    await UserService(session).update_profile(user, weight_kg=None)
    await state.clear()
    await _show_summary(cq.message, user)
    await cq.answer("Очищено")


# =============================================================== FULL WIZARD
@router.callback_query(F.data == "prof:wizard")
async def wizard_start(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProfileWizardFSM.waiting_sex)
    await cq.message.edit_text(
        "Шаг 1/6 — Пол:", reply_markup=_sex_kb("prof:wz:sex", with_skip=True)
    )
    await cq.answer()


@router.callback_query(ProfileWizardFSM.waiting_sex, F.data.startswith("prof:wz:sex:"))
async def wz_sex(cq: CallbackQuery, state: FSMContext) -> None:
    val = cq.data.split(":")[3]
    if val != "skip":
        await state.update_data(sex=val)
    await state.set_state(ProfileWizardFSM.waiting_birth)
    await cq.message.edit_text(
        "Шаг 2/6 — Дата рождения, ДД.ММ.ГГГГ (или «Пропустить»):",
        reply_markup=skip_cancel_kb(),
    )
    await cq.answer()


@router.message(ProfileWizardFSM.waiting_birth)
async def wz_birth_text(message: Message, state: FSMContext) -> None:
    parsed = _parse_birth(message.text or "")
    if parsed is None:
        await message.answer("Не понял дату. Формат: ДД.ММ.ГГГГ")
        return
    await state.update_data(birth_date=parsed.isoformat())
    await state.set_state(ProfileWizardFSM.waiting_height)
    await message.answer("Шаг 3/6 — Рост в см:", reply_markup=skip_cancel_kb())


@router.callback_query(ProfileWizardFSM.waiting_birth, F.data == "skip")
async def wz_birth_skip(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProfileWizardFSM.waiting_height)
    await cq.message.edit_text("Шаг 3/6 — Рост в см:", reply_markup=skip_cancel_kb())
    await cq.answer()


@router.message(ProfileWizardFSM.waiting_height)
async def wz_height_text(message: Message, state: FSMContext) -> None:
    h = _parse_positive(message.text or "", lo=80, hi=260)
    if h is None:
        await message.answer("Нужно число от 80 до 260.")
        return
    await state.update_data(height_cm=h)
    await state.set_state(ProfileWizardFSM.waiting_weight)
    await message.answer("Шаг 4/6 — Вес в кг:", reply_markup=skip_cancel_kb())


@router.callback_query(ProfileWizardFSM.waiting_height, F.data == "skip")
async def wz_height_skip(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProfileWizardFSM.waiting_weight)
    await cq.message.edit_text("Шаг 4/6 — Вес в кг:", reply_markup=skip_cancel_kb())
    await cq.answer()


@router.message(ProfileWizardFSM.waiting_weight)
async def wz_weight_text(message: Message, state: FSMContext) -> None:
    w = _parse_positive(message.text or "", lo=20, hi=400)
    if w is None:
        await message.answer("Нужно число от 20 до 400.")
        return
    await state.update_data(weight_kg=w)
    await state.set_state(ProfileWizardFSM.waiting_smoker)
    await message.answer(
        "Шаг 5/6 — Курите?", reply_markup=_yes_no_skip_kb("prof:wz:smoker")
    )


@router.callback_query(ProfileWizardFSM.waiting_weight, F.data == "skip")
async def wz_weight_skip(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProfileWizardFSM.waiting_smoker)
    await cq.message.edit_text(
        "Шаг 5/6 — Курите?", reply_markup=_yes_no_skip_kb("prof:wz:smoker")
    )
    await cq.answer()


@router.callback_query(ProfileWizardFSM.waiting_smoker, F.data.startswith("prof:wz:smoker:"))
async def wz_smoker(cq: CallbackQuery, state: FSMContext) -> None:
    val = cq.data.split(":")[3]
    if val != "skip":
        await state.update_data(is_smoker=(val == "yes"))
    await state.set_state(ProfileWizardFSM.waiting_diabetes)
    await cq.message.edit_text(
        "Шаг 6/6 — Диабет 2 типа?",
        reply_markup=_yes_no_skip_kb("prof:wz:diabetes"),
    )
    await cq.answer()


@router.callback_query(ProfileWizardFSM.waiting_diabetes, F.data.startswith("prof:wz:diabetes:"))
async def wz_diabetes(cq: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    val = cq.data.split(":")[3]
    data = await state.get_data()
    patch: dict[str, object] = {}
    if "sex" in data:
        patch["sex"] = Sex(data["sex"])
    if "birth_date" in data:
        patch["birth_date"] = date.fromisoformat(data["birth_date"])
    if "height_cm" in data:
        patch["height_cm"] = data["height_cm"]
    if "weight_kg" in data:
        patch["weight_kg"] = data["weight_kg"]
    if "is_smoker" in data:
        patch["is_smoker"] = data["is_smoker"]
    if val != "skip":
        patch["has_diabetes"] = (val == "yes")

    if patch:
        await UserService(session).update_profile(user, **patch)
    await state.clear()
    await cq.message.edit_text(
        _fmt(user) + "\n\n✅ Профиль обновлён.",
        reply_markup=profile_menu(),
    )
    await cq.answer("Готово")
