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
from app.bot.states.nutrition import NutritionFSM
from app.db.models import User
from app.domain.enums import MealType
from app.domain.schemas import MealIn
from app.services.nutrition import NutritionService
from app.utils.i18n import t
from app.utils.time import now_utc, parse_user_datetime

router = Router(name="nutrition")


def _meal_kb() -> InlineKeyboardMarkup:
    labels = {
        MealType.BREAKFAST: "Завтрак",
        MealType.LUNCH: "Обед",
        MealType.DINNER: "Ужин",
        MealType.SNACK: "Перекус",
    }
    rows = [
        [InlineKeyboardButton(text=labels[m], callback_data=f"meal:{m.value}")]
        for m in MealType
    ]
    rows.append([InlineKeyboardButton(text=t("cancel"), callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "rec:meal")
async def start(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(NutritionFSM.waiting_time)
    await cq.message.edit_text(t("ask_time"), reply_markup=now_or_input_kb())
    await cq.answer()


@router.callback_query(NutritionFSM.waiting_time, F.data == "time:now")
async def time_now(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(eaten_at=now_utc().isoformat())
    await state.set_state(NutritionFSM.waiting_meal_type)
    await cq.message.edit_text("Тип приёма пищи:", reply_markup=_meal_kb())
    await cq.answer()


@router.message(NutritionFSM.waiting_time)
async def time_input(message: Message, state: FSMContext, user: User) -> None:
    try:
        dt = parse_user_datetime(message.text or "", user.timezone)
    except ValueError:
        await message.answer("Не понял время.")
        return
    await state.update_data(eaten_at=dt.isoformat())
    await state.set_state(NutritionFSM.waiting_meal_type)
    await message.answer("Тип приёма пищи:", reply_markup=_meal_kb())


@router.callback_query(NutritionFSM.waiting_meal_type, F.data.startswith("meal:"))
async def chose_meal(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(meal_type=cq.data.split(":")[1])
    await state.set_state(NutritionFSM.waiting_tags)
    await cq.message.edit_text(
        "Теги (через запятую): солёное, фастфуд, овощи… (или «Пропустить»):",
        reply_markup=skip_cancel_kb(),
    )
    await cq.answer()


@router.callback_query(NutritionFSM.waiting_tags, F.data == "skip")
async def skip_tags(cq: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    await state.update_data(tags=[])
    await _save_and_finish(cq.message, state, session, user)
    await cq.answer()


@router.message(NutritionFSM.waiting_tags)
async def tags_input(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    tags = [s.strip() for s in (message.text or "").split(",") if s.strip()]
    await state.update_data(tags=tags)
    await _save_and_finish(message, state, session, user)


async def _save_and_finish(target, state: FSMContext, session: AsyncSession, user: User) -> None:
    data = await state.get_data()
    payload = MealIn(
        eaten_at=datetime.fromisoformat(data["eaten_at"]),
        meal_type=MealType(data["meal_type"]),
        tags=data.get("tags") or [],
    )
    await NutritionService(session).add(user, payload)
    await state.clear()
    await target.answer("✅ Сохранено.", reply_markup=record_menu())
