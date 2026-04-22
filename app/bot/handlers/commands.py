"""Shortcut command handlers — mirrors the inline-button flow entry points."""
from __future__ import annotations

import uuid

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import cancel_kb, now_or_input_kb
from app.bot.keyboards.patient import (
    history_menu,
    main_menu,
    record_menu,
    reports_menu,
    settings_menu,
)
from app.bot.states.glucose import GlucoseFSM
from app.bot.states.labs import LabFSM
from app.bot.states.medications import MedIntakeFSM
from app.bot.states.nutrition import NutritionFSM
from app.bot.states.pressure import PressureFSM
from app.bot.states.symptoms import SymptomFSM
from app.db.models import User
from app.domain.enums import UserRole
from app.services.medications import MedicationService
from app.utils.i18n import t

router = Router(name="commands")

_HELP_TEXT = (
    "<b>VitalTrack — команды</b>\n\n"
    "<b>Запись показателей:</b>\n"
    "/pressure — давление\n"
    "/glucose — глюкоза\n"
    "/symptoms — симптомы и самочувствие\n"
    "/meal — приём пищи\n"
    "/labs — лабораторные анализы\n"
    "/med — отметить приём лекарства\n\n"
    "<b>Данные:</b>\n"
    "/meds — список препаратов\n"
    "/history — история измерений\n"
    "/report — отчёт\n\n"
    "<b>Прочее:</b>\n"
    "/settings — настройки\n"
    "/invite_doctor — пригласить врача (QR-код)\n"
    "/cancel — отменить текущий ввод\n"
    "/forget_me — удалить все мои данные\n"
)


@router.message(Command("pressure"))
async def cmd_pressure(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(PressureFSM.waiting_time)
    await state.update_data(session_uuid=str(uuid.uuid4()))
    await message.answer(t("ask_time"), reply_markup=now_or_input_kb())


@router.message(Command("glucose"))
async def cmd_glucose(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(GlucoseFSM.waiting_time)
    await message.answer(t("ask_time"), reply_markup=now_or_input_kb())


@router.message(Command("symptoms"))
async def cmd_symptoms(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(SymptomFSM.waiting_time)
    await message.answer(t("ask_time"), reply_markup=now_or_input_kb())


@router.message(Command("meal"))
async def cmd_meal(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(NutritionFSM.waiting_time)
    await message.answer(t("ask_time"), reply_markup=now_or_input_kb())


@router.message(Command("labs"))
async def cmd_labs(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(LabFSM.waiting_date)
    await message.answer(
        "Дата сдачи анализа (например 02.04 09:00 или «Сейчас»):",
        reply_markup=now_or_input_kb(),
    )


@router.message(Command("med"))
async def cmd_med(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    await state.clear()
    meds = await MedicationService(session).list_active(user)
    if not meds:
        await message.answer(
            "Нет активных препаратов. Добавьте их в /meds",
            reply_markup=record_menu(),
        )
        return
    rows = [[InlineKeyboardButton(text=m.name, callback_data=f"intake:{m.id}")] for m in meds]
    rows.append([InlineKeyboardButton(text=t("cancel"), callback_data="cancel")])
    await state.set_state(MedIntakeFSM.waiting_medication)
    await message.answer(
        "Какой препарат приняли?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.message(Command("meds"))
async def cmd_meds(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    await state.clear()
    from app.services.medications import MedicationService as MS
    meds = await MS(session).list_active(user)
    rows: list[list[InlineKeyboardButton]] = []
    for m in meds:
        rows.append([InlineKeyboardButton(text=f"❌ {m.name}", callback_data=f"med:del:{m.id}")])
    rows.append([InlineKeyboardButton(text="➕ Добавить препарат", callback_data="med:new")])
    rows.append([InlineKeyboardButton(text=t("back"), callback_data="menu:home")])
    txt = "Лекарства:\n" + (
        "\n".join(f"  • {m.name}" + (f" ({m.dose})" if m.dose else "") for m in meds)
        or "  пусто"
    )
    await message.answer(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.message(Command("report"))
async def cmd_report(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отчёт — выберите период:", reply_markup=reports_menu())


@router.message(Command("history"))
async def cmd_history(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("История:", reply_markup=history_menu())


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Настройки:", reply_markup=settings_menu())


@router.message(Command("help"))
async def cmd_help(message: Message, user: User) -> None:
    text = _HELP_TEXT
    if user.role == UserRole.DOCTOR:
        text += "/invite_patient — пригласить пациента (QR-код)\n"
    await message.answer(text)
