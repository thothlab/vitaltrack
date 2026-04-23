from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import cancel_kb
from app.bot.keyboards.patient import main_menu, record_menu
from app.bot.states.medications import MedCreateFSM, MedIntakeFSM
from app.db.models import User
from app.domain.enums import MedScheduleType, UserRole
from app.domain.schemas import IntakeIn, MedicationIn
from app.scheduler.scheduler import schedule_medication, unschedule_medication
from app.services.medications import MedicationService
from app.utils.i18n import t
from app.utils.time import now_utc

router = Router(name="medications")


@router.callback_query(F.data == "menu:meds")
async def meds_home(cq: CallbackQuery, session: AsyncSession, user: User) -> None:
    meds = await MedicationService(session).list_active(user)
    rows: list[list[InlineKeyboardButton]] = []
    for m in meds:
        rows.append([InlineKeyboardButton(
            text=f"❌ {m.name}", callback_data=f"med:del:{m.id}",
        )])
    rows.append([InlineKeyboardButton(text="➕ Добавить препарат", callback_data="med:new")])
    rows.append([InlineKeyboardButton(text=t("back"), callback_data="menu:home")])
    txt = "Лекарства:\n" + ("\n".join(f"  • {m.name}" + (f" ({m.dose})" if m.dose else "") for m in meds) or "  пусто")
    await cq.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cq.answer()


@router.callback_query(F.data == "med:new")
async def med_new(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(MedCreateFSM.waiting_name)
    await cq.message.edit_text("Название препарата:", reply_markup=cancel_kb())
    await cq.answer()


@router.message(MedCreateFSM.waiting_name)
async def med_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Название не может быть пустым.")
        return
    await state.update_data(name=name)
    await state.set_state(MedCreateFSM.waiting_dose)
    await message.answer("Дозировка (например «5 мг», «1 табл.») или «-»:", reply_markup=cancel_kb())


@router.message(MedCreateFSM.waiting_dose)
async def med_dose(message: Message, state: FSMContext) -> None:
    dose = (message.text or "").strip()
    if dose in ("-", ""):
        dose = None
    await state.update_data(dose=dose)
    await state.set_state(MedCreateFSM.waiting_schedule_type)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="В фикс. время", callback_data="msched:fixed")],
        [InlineKeyboardButton(text="Каждые N часов", callback_data="msched:interval")],
        [InlineKeyboardButton(text="По требованию", callback_data="msched:prn")],
        [InlineKeyboardButton(text=t("cancel"), callback_data="cancel")],
    ])
    await message.answer("Расписание:", reply_markup=kb)


@router.callback_query(MedCreateFSM.waiting_schedule_type, F.data == "msched:prn")
async def msched_prn(cq: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    data = await state.get_data()
    payload = MedicationIn(
        name=data["name"], dose=data.get("dose"),
        schedule_type=MedScheduleType.AS_NEEDED, schedule_data={},
    )
    med = await MedicationService(session).add(user, payload)
    await session.flush()
    await schedule_medication(med, user)
    await state.clear()
    await cq.message.edit_text(
        f"✅ Добавлено: {med.name} (по требованию).",
        reply_markup=main_menu(is_doctor=(user.role == UserRole.DOCTOR)),
    )
    await cq.answer()


@router.callback_query(MedCreateFSM.waiting_schedule_type, F.data == "msched:fixed")
async def msched_fixed(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(schedule_kind="fixed")
    await state.set_state(MedCreateFSM.waiting_schedule_data)
    await cq.message.edit_text(
        "Введите время приёма через запятую, формат HH:MM\nНапример: 08:00, 14:00, 20:00",
        reply_markup=cancel_kb(),
    )
    await cq.answer()


@router.callback_query(MedCreateFSM.waiting_schedule_type, F.data == "msched:interval")
async def msched_interval(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(schedule_kind="interval")
    await state.set_state(MedCreateFSM.waiting_schedule_data)
    await cq.message.edit_text(
        "Введите интервал и якорное время, формат «N HH:MM»\n"
        "Например: «8 08:00» — каждые 8 часов начиная с 08:00",
        reply_markup=cancel_kb(),
    )
    await cq.answer()


@router.message(MedCreateFSM.waiting_schedule_data)
async def msched_data(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    data = await state.get_data()
    kind = data.get("schedule_kind")
    text = (message.text or "").strip()
    try:
        if kind == "fixed":
            times = [chunk.strip() for chunk in text.split(",")]
            for t_ in times:
                hh, mm = t_.split(":")
                int(hh); int(mm)
            schedule_data = {"times": times}
            sched_type = MedScheduleType.FIXED_TIMES
        else:
            n_str, anchor = text.split()
            interval = int(n_str)
            hh, mm = anchor.split(":")
            int(hh); int(mm)
            schedule_data = {"interval_hours": interval, "anchor": anchor}
            sched_type = MedScheduleType.EVERY_N_HOURS
    except Exception:
        await message.answer("Не разобрал. Попробуйте ещё раз.")
        return

    payload = MedicationIn(
        name=data["name"], dose=data.get("dose"),
        schedule_type=sched_type, schedule_data=schedule_data,
    )
    med = await MedicationService(session).add(user, payload)
    await session.flush()
    await schedule_medication(med, user)
    await state.clear()
    await message.answer(
        f"✅ {med.name}: расписание установлено, напоминания включены.",
        reply_markup=main_menu(is_doctor=(user.role == UserRole.DOCTOR)),
    )


@router.callback_query(F.data.startswith("med:del:"))
async def med_del(cq: CallbackQuery, session: AsyncSession, user: User) -> None:
    med_id = int(cq.data.split(":")[2])
    await MedicationService(session).deactivate(med_id)
    unschedule_medication(med_id)
    await cq.answer("Удалено", show_alert=False)
    await meds_home(cq, session, user)


# ----- ad-hoc intake -----
@router.callback_query(F.data == "rec:med")
async def rec_med(cq: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    meds = await MedicationService(session).list_active(user)
    if not meds:
        await cq.answer("Нет активных препаратов", show_alert=True)
        return
    rows = [[InlineKeyboardButton(text=m.name, callback_data=f"intake:{m.id}")] for m in meds]
    rows.append([InlineKeyboardButton(text=t("cancel"), callback_data="cancel")])
    await state.set_state(MedIntakeFSM.waiting_medication)
    await cq.message.edit_text("Какой препарат приняли?",
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cq.answer()


_LINK_WINDOW_MINUTES = 60  # link ad-hoc intake to scheduled slot if within this window


@router.callback_query(MedIntakeFSM.waiting_medication, F.data.startswith("intake:"))
async def intake_now(cq: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    med_id = int(cq.data.split(":")[1])
    now = now_utc()
    svc = MedicationService(session)

    # Try to link to the nearest scheduled slot within ±LINK_WINDOW_MINUTES
    med = await svc.repo.by_id(med_id)
    linked_slot = None
    if med is not None:
        w_start = now - timedelta(minutes=_LINK_WINDOW_MINUTES)
        w_end = now + timedelta(minutes=_LINK_WINDOW_MINUTES)
        slots = MedicationService.expected_intakes([med], w_start, w_end, user.timezone)
        candidates = slots.get(med_id, [])
        if candidates:
            linked_slot = min(candidates, key=lambda s: abs((s - now).total_seconds()))

    if linked_slot is not None:
        await svc.mark_scheduled(user, med_id, linked_slot, taken=True)
    else:
        await svc.log_intake(user, IntakeIn(
            medication_id=med_id, taken_at=now, taken=True,
        ))

    await state.clear()
    await cq.message.edit_text("✅ Приём отмечен.", reply_markup=record_menu())
    await cq.answer()


# ----- callbacks from reminder messages -----
@router.callback_query(F.data.startswith("med_take:"))
async def reminder_take(cq: CallbackQuery, session: AsyncSession, user: User) -> None:
    _, med_id, slot_iso = cq.data.split(":", 2)
    slot = datetime.fromisoformat(slot_iso)
    await MedicationService(session).mark_scheduled(
        user, int(med_id), scheduled_at=slot, taken=True,
    )
    await cq.message.edit_text(
        "✅ Приём отмечен.",
        reply_markup=main_menu(is_doctor=(user.role == UserRole.DOCTOR)),
    )
    await cq.answer()


@router.callback_query(F.data.startswith("med_skip:"))
async def reminder_skip(cq: CallbackQuery, session: AsyncSession, user: User) -> None:
    _, med_id, slot_iso = cq.data.split(":", 2)
    slot = datetime.fromisoformat(slot_iso)
    await MedicationService(session).mark_scheduled(
        user, int(med_id), scheduled_at=slot, taken=False,
    )
    await cq.message.edit_text(
        "⏭ Пропуск зарегистрирован.",
        reply_markup=main_menu(is_doctor=(user.role == UserRole.DOCTOR)),
    )
    await cq.answer()
