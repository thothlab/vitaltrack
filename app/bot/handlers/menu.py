from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.bot.keyboards.patient import (
    calc_menu,
    history_menu,
    main_menu,
    record_menu,
    reports_menu,
    settings_menu,
)
from app.bot.keyboards.doctor import doctor_menu
from app.db.models import User
from app.domain.enums import UserRole
from app.repositories.gi import GIRepository
from app.repositories.glucose import GlucoseRepository
from app.repositories.headache import HeadacheRepository
from app.repositories.medications import MedicationRepository
from app.repositories.pressure import PressureRepository
from app.repositories.symptoms import SymptomRepository
from app.utils.time import days_ago_utc, format_user_dt, now_utc
from sqlalchemy.ext.asyncio import AsyncSession

router = Router(name="menu")


@router.callback_query(F.data == "menu:home")
async def home(cq: CallbackQuery, state: FSMContext, user: User) -> None:
    await state.clear()
    await cq.message.edit_text(
        "Главное меню:",
        reply_markup=main_menu(is_doctor=(user.role == UserRole.DOCTOR)),
    )
    await cq.answer()


@router.callback_query(F.data == "menu:record")
async def record(cq: CallbackQuery) -> None:
    await cq.message.edit_text("Что записываем?", reply_markup=record_menu())
    await cq.answer()


@router.callback_query(F.data == "menu:history")
async def history(cq: CallbackQuery) -> None:
    await cq.message.edit_text("Какую историю показать?", reply_markup=history_menu())
    await cq.answer()


@router.callback_query(F.data == "menu:reports")
async def reports(cq: CallbackQuery) -> None:
    await cq.message.edit_text("Период отчёта?", reply_markup=reports_menu())
    await cq.answer()


@router.callback_query(F.data == "menu:calc")
async def calc(cq: CallbackQuery) -> None:
    await cq.message.edit_text(
        "🧮 <b>Медицинские калькуляторы</b>\n\n"
        "Считают по реальным формулам, не дают диагноз — только ориентир для "
        "обсуждения с врачом.\n\n"
        "• <b>SCORE2</b> — 10-летний риск сердечно-сосудистых событий "
        "(ESC 2021), для возраста 40–69.\n"
        "• <b>ИМТ / BMI</b> — индекс массы тела (рост/вес).\n"
        "• <b>СКФ / eGFR</b> — скорость клубочковой фильтрации "
        "(CKD-EPI 2021), стадия по K/DOQI.\n"
        "• <b>HOMA-IR</b> — индекс инсулинорезистентности по глюкозе и "
        "инсулину натощак.",
        reply_markup=calc_menu(),
    )
    await cq.answer()


@router.callback_query(F.data == "menu:settings")
async def settings(cq: CallbackQuery) -> None:
    await cq.message.edit_text("Настройки:", reply_markup=settings_menu())
    await cq.answer()


@router.callback_query(F.data == "menu:doctor")
async def doctor(cq: CallbackQuery, user: User) -> None:
    if user.role != UserRole.DOCTOR:
        await cq.answer("Доступно только врачам", show_alert=True)
        return
    await cq.message.edit_text("Кабинет врача:", reply_markup=doctor_menu())
    await cq.answer()


# ---------------- history views ----------------
@router.callback_query(F.data == "hist:pressure")
async def hist_pressure(cq: CallbackQuery, user: User, session: AsyncSession) -> None:
    recs = await PressureRepository(session).latest(user.id, limit=10)
    if not recs:
        txt = "Нет записей"
    else:
        lines = ["Последние измерения АД:"]
        for r in recs:
            lines.append(
                f"  {format_user_dt(r.measured_at, user.timezone)} · "
                f"{r.systolic}/{r.diastolic}"
                + (f" · ЧСС {r.pulse}" if r.pulse else "")
            )
        txt = "\n".join(lines)
    await cq.message.edit_text(txt, reply_markup=history_menu())
    await cq.answer()


@router.callback_query(F.data == "hist:glucose")
async def hist_glucose(cq: CallbackQuery, user: User, session: AsyncSession) -> None:
    recs = await GlucoseRepository(session).latest(user.id, limit=10)
    if not recs:
        txt = "Нет записей"
    else:
        lines = ["Последние измерения глюкозы:"]
        for r in recs:
            lines.append(
                f"  {format_user_dt(r.measured_at, user.timezone)} · "
                f"{r.value_mmol} ммоль/л · {r.context.value}"
            )
        txt = "\n".join(lines)
    await cq.message.edit_text(txt, reply_markup=history_menu())
    await cq.answer()


@router.callback_query(F.data == "hist:meds")
async def hist_meds(cq: CallbackQuery, user: User, session: AsyncSession) -> None:
    rows = await MedicationRepository(session).recent_intakes_with_med(user.id, limit=20)
    if not rows:
        txt = "История приёма лекарств пуста"
    else:
        lines = ["<b>История приёма лекарств (последние 20):</b>"]
        for intake, med in rows:
            ts = intake.taken_at or intake.scheduled_at
            time_str = format_user_dt(ts, user.timezone) if ts else "—"
            status = "✅" if intake.taken else "❌"
            dose = f" {med.dose}" if med.dose else ""
            lines.append(f"{status} {time_str} · {med.name}{dose}")
        txt = "\n".join(lines)
    await cq.message.edit_text(txt, reply_markup=history_menu())
    await cq.answer()


@router.callback_query(F.data == "hist:gi")
async def hist_gi(cq: CallbackQuery, user: User, session: AsyncSession) -> None:
    recs = await GIRepository(session).latest(user.id, limit=10)
    if not recs:
        txt = "Нет записей ЖКТ"
    else:
        lines = ["<b>ЖКТ — последние записи:</b>"]
        bristol_desc = {1: "запор", 2: "комки", 3: "трещины", 4: "норма",
                        5: "мягкие", 6: "кашица", 7: "диарея"}
        for r in recs:
            parts = []
            if r.pain is not None:
                parts.append(f"боль {r.pain}")
            if r.nausea is not None:
                parts.append(f"тошнота {r.nausea}")
            if r.heartburn is not None:
                parts.append(f"изжога {r.heartburn}")
            if r.bloating is not None:
                parts.append(f"вздутие {r.bloating}")
            if r.stool_bristol is not None:
                parts.append(f"стул {r.stool_bristol} ({bristol_desc.get(r.stool_bristol, '')})")
            summary = " · ".join(parts) if parts else "—"
            lines.append(f"  {format_user_dt(r.occurred_at, user.timezone)} · {summary}")
        txt = "\n".join(lines)
    await cq.message.edit_text(txt, reply_markup=history_menu())
    await cq.answer()


@router.callback_query(F.data == "hist:headache")
async def hist_headache(cq: CallbackQuery, user: User, session: AsyncSession) -> None:
    recs = await HeadacheRepository(session).latest(user.id, limit=10)
    if not recs:
        txt = "Нет записей о головной боли"
    else:
        loc_ru = {"left": "левая", "right": "правая", "bilateral": "обе стороны",
                  "whole": "вся голова"}
        char_ru = {"pulsating": "пульсирующая", "pressing": "давящая",
                   "stabbing": "колющая", "other": "другая"}
        dis_ru = {0: "без ограничений", 1: "лёгкие", 2: "умеренные", 3: "тяжёлые"}
        lines = ["<b>Головная боль — последние записи:</b>"]
        for r in recs:
            parts = [f"интенс. {r.intensity}/10"]
            if r.location:
                parts.append(loc_ru.get(r.location.value, r.location.value))
            if r.character:
                parts.append(char_ru.get(r.character.value, r.character.value))
            if r.duration_hours:
                parts.append(f"{r.duration_hours:.1f} ч")
            if r.disability is not None:
                parts.append(dis_ru.get(r.disability, str(r.disability)))
            assoc = []
            if r.nausea:
                assoc.append("тошнота")
            if r.photophobia:
                assoc.append("светобоязнь")
            if r.phonophobia:
                assoc.append("звукобоязнь")
            if r.aura:
                assoc.append("аура")
            if assoc:
                parts.append(", ".join(assoc))
            lines.append(f"  {format_user_dt(r.started_at, user.timezone)} · {' · '.join(parts)}")
        txt = "\n".join(lines)
    await cq.message.edit_text(txt, reply_markup=history_menu())
    await cq.answer()


@router.callback_query(F.data == "hist:symptoms")
async def hist_symptoms(cq: CallbackQuery, user: User, session: AsyncSession) -> None:
    end = now_utc()
    start = days_ago_utc(14, user.timezone)
    recs = await SymptomRepository(session).list_between(user.id, start, end)
    if not recs:
        txt = "Нет записей за 14 дней"
    else:
        lines = ["Симптомы за 14 дней:"]
        for r in recs[-10:]:
            sym = ", ".join(r.symptoms) if r.symptoms else "—"
            lines.append(
                f"  {format_user_dt(r.occurred_at, user.timezone)} · "
                f"{r.wellbeing.value} · {sym}"
            )
        txt = "\n".join(lines)
    await cq.message.edit_text(txt, reply_markup=history_menu())
    await cq.answer()
