from __future__ import annotations

from datetime import datetime
from io import BytesIO

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import cancel_kb
from app.bot.keyboards.patient import report_format_menu, reports_menu
from app.bot.states.reports import ReportFSM
from app.db.models import User
from app.domain.enums import ReportFormat, ReportPeriod
from app.reports import render_csv_bundle, render_pdf, render_text
from app.services.reports import ReportService
from app.utils.time import parse_user_datetime

router = Router(name="reports")


@router.callback_query(F.data.startswith("rep:period:"))
async def chose_period(cq: CallbackQuery, state: FSMContext) -> None:
    period = cq.data.split(":")[2]
    await state.set_state(ReportFSM.waiting_format)
    await state.update_data(period=period)
    if period == "custom":
        await state.set_state(ReportFSM.waiting_custom_start)
        await cq.message.edit_text(
            "Введите начало периода (DD.MM.YYYY):", reply_markup=cancel_kb()
        )
    else:
        await cq.message.edit_text("Формат отчёта:", reply_markup=report_format_menu())
    await cq.answer()


@router.message(ReportFSM.waiting_custom_start)
async def custom_start(message: Message, state: FSMContext, user: User) -> None:
    try:
        dt = parse_user_datetime(f"{message.text.strip()} 00:00", user.timezone)
    except ValueError:
        await message.answer("Не понял дату. Пример: 01.03.2026")
        return
    await state.update_data(custom_start=dt.isoformat())
    await state.set_state(ReportFSM.waiting_custom_end)
    await message.answer("Введите конец периода (DD.MM.YYYY):", reply_markup=cancel_kb())


@router.message(ReportFSM.waiting_custom_end)
async def custom_end(message: Message, state: FSMContext, user: User) -> None:
    try:
        dt = parse_user_datetime(f"{message.text.strip()} 23:59", user.timezone)
    except ValueError:
        await message.answer("Не понял дату.")
        return
    await state.update_data(custom_end=dt.isoformat())
    await state.set_state(ReportFSM.waiting_format)
    await message.answer("Формат отчёта:", reply_markup=report_format_menu())


@router.callback_query(ReportFSM.waiting_format, F.data.startswith("rep:fmt:"))
async def make_report(cq: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    fmt = ReportFormat(cq.data.split(":")[2])
    data = await state.get_data()
    period = ReportPeriod(data["period"])
    cs = ce = None
    if period == ReportPeriod.CUSTOM:
        cs = datetime.fromisoformat(data["custom_start"])
        ce = datetime.fromisoformat(data["custom_end"])
    report = await ReportService(session).aggregate(user, period, cs, ce)
    await state.clear()

    if fmt == ReportFormat.TEXT:
        await cq.message.edit_text(render_text(report), reply_markup=reports_menu())
    elif fmt == ReportFormat.PDF:
        pdf = render_pdf(report)
        await cq.message.delete()
        await cq.message.answer_document(
            BufferedInputFile(pdf, filename="vitaltrack-report.pdf"),
            caption="PDF готов",
        )
        await cq.message.answer("Меню отчётов:", reply_markup=reports_menu())
    else:
        bundle = render_csv_bundle(report)
        await cq.message.delete()
        await cq.message.answer_document(
            BufferedInputFile(bundle, filename="vitaltrack-csv.zip"),
            caption="CSV-архив готов",
        )
        await cq.message.answer("Меню отчётов:", reply_markup=reports_menu())
    await cq.answer()
