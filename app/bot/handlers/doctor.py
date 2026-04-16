from __future__ import annotations

from io import BytesIO

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common import cancel_kb
from app.bot.keyboards.doctor import (
    doctor_menu,
    patient_view_kb,
    patients_kb,
    thread_view_kb,
    threads_kb,
)
from app.bot.states.doctor import DoctorMessageFSM
from app.db.models import User
from app.domain.enums import ReportPeriod, UserRole
from app.reports import render_pdf
from app.repositories.alerts import AlertRepository
from app.repositories.users import UserRepository
from app.services.messaging import MessagingService
from app.services.reports import ReportService
from app.services.users import UserService
from app.utils.time import format_user_dt

router = Router(name="doctor")


def _ensure_doctor(user: User, cq: CallbackQuery) -> bool:
    if user.role != UserRole.DOCTOR:
        cq.bot.loop.create_task(cq.answer("Только для врачей", show_alert=True))
        return False
    return True


@router.callback_query(F.data == "doc:patients")
async def patients_list(cq: CallbackQuery, session: AsyncSession, user: User) -> None:
    if user.role != UserRole.DOCTOR:
        await cq.answer("Только для врачей", show_alert=True); return
    patients = await UserService(session).list_patients_for(user)
    if not patients:
        await cq.message.edit_text(
            "Нет привязанных пациентов. Дайте им свой Telegram ID для привязки в настройках.",
            reply_markup=doctor_menu(),
        )
    else:
        await cq.message.edit_text("Ваши пациенты:", reply_markup=patients_kb(patients))
    await cq.answer()


@router.callback_query(F.data.startswith("doc:patient:"))
async def patient_view(cq: CallbackQuery, session: AsyncSession, user: User) -> None:
    if user.role != UserRole.DOCTOR:
        await cq.answer("Только для врачей", show_alert=True); return
    patient_id = int(cq.data.split(":")[2])
    patient = await UserRepository(session).by_id(patient_id)
    if patient is None or patient.doctor_id != user.id:
        await cq.answer("Нет доступа", show_alert=True); return
    alerts = await AlertRepository(session).open_for_user(patient.id)
    txt = f"<b>{patient.full_name or patient.telegram_id}</b>\n"
    if alerts:
        txt += "\nОткрытые алёрты:\n"
        for a in alerts[:5]:
            txt += f"  ⚠ {a.summary} ({format_user_dt(a.created_at, user.timezone)})\n"
    else:
        txt += "\nНет открытых алёртов."
    await cq.message.edit_text(txt, reply_markup=patient_view_kb(patient.id))
    await cq.answer()


@router.callback_query(F.data.startswith("doc:report:"))
async def patient_report(cq: CallbackQuery, session: AsyncSession, user: User) -> None:
    if user.role != UserRole.DOCTOR:
        await cq.answer("Только для врачей", show_alert=True); return
    _, _, pid, period = cq.data.split(":")
    patient = await UserRepository(session).by_id(int(pid))
    if patient is None or patient.doctor_id != user.id:
        await cq.answer("Нет доступа", show_alert=True); return
    data = await ReportService(session).aggregate(patient, ReportPeriod(period))
    pdf = render_pdf(data)
    await cq.message.answer_document(
        BufferedInputFile(pdf, filename=f"patient-{patient.id}-{period}.pdf"),
        caption=f"Отчёт по пациенту за {period}",
    )
    await cq.answer()


# ----- threads -----
@router.callback_query(F.data == "doc:threads")
async def doc_threads(cq: CallbackQuery, session: AsyncSession, user: User) -> None:
    threads = await MessagingService(session).threads_for(user)
    if not threads:
        await cq.message.edit_text("Нет диалогов.", reply_markup=doctor_menu())
    else:
        await cq.message.edit_text(
            "Сообщения:", reply_markup=threads_kb(threads, me_role_doctor=True)
        )
    await cq.answer()


@router.callback_query(F.data.startswith("doc:msg:"))
async def doc_msg_open(cq: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    if user.role != UserRole.DOCTOR:
        await cq.answer("Только для врачей", show_alert=True); return
    pid = int(cq.data.split(":")[2])
    patient = await UserRepository(session).by_id(pid)
    if patient is None or patient.doctor_id != user.id:
        await cq.answer("Нет доступа", show_alert=True); return
    thread = await MessagingService(session).open_thread(user, patient)
    await state.set_state(DoctorMessageFSM.waiting_body)
    await state.update_data(thread_id=thread.id, recipient_tg=patient.telegram_id)
    await cq.message.edit_text(
        f"Сообщение пациенту {patient.full_name or patient.telegram_id}:",
        reply_markup=cancel_kb(),
    )
    await cq.answer()


@router.callback_query(F.data.startswith("thread:open:"))
async def thread_open(cq: CallbackQuery, session: AsyncSession, user: User) -> None:
    thread_id = int(cq.data.split(":")[2])
    thread = await MessagingService(session).thread(thread_id)
    if thread is None or user.id not in (thread.doctor_id, thread.patient_id):
        await cq.answer("Нет доступа", show_alert=True); return
    msgs = await MessagingService(session).messages(thread_id, user)
    if not msgs:
        body = "Пусто."
    else:
        body = "\n".join(
            f"{format_user_dt(m.created_at, user.timezone)}  "
            f"{'ВЫ' if m.sender_id == user.id else 'СОБЕСЕДНИК'}: {m.body}"
            for m in msgs[-20:]
        )
    await cq.message.edit_text(body, reply_markup=thread_view_kb(thread_id))
    await cq.answer()


@router.callback_query(F.data.startswith("thread:reply:"))
async def thread_reply(cq: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    thread_id = int(cq.data.split(":")[2])
    thread = await MessagingService(session).thread(thread_id)
    if thread is None or user.id not in (thread.doctor_id, thread.patient_id):
        await cq.answer("Нет доступа", show_alert=True); return
    other_id = thread.patient_id if user.id == thread.doctor_id else thread.doctor_id
    other = await UserRepository(session).by_id(other_id)
    await state.set_state(DoctorMessageFSM.waiting_body)
    await state.update_data(thread_id=thread.id, recipient_tg=other.telegram_id if other else None)
    await cq.message.edit_text("Введите сообщение:", reply_markup=cancel_kb())
    await cq.answer()


@router.message(DoctorMessageFSM.waiting_body)
async def thread_send(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    body = (message.text or "").strip()
    if not body:
        await message.answer("Сообщение не может быть пустым.")
        return
    data = await state.get_data()
    thread = await MessagingService(session).thread(int(data["thread_id"]))
    if thread is None:
        await message.answer("Диалог не найден.")
        await state.clear()
        return
    await MessagingService(session).send(thread, user, body)
    recipient_tg = data.get("recipient_tg")
    if recipient_tg:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Открыть", callback_data=f"thread:open:{thread.id}"),
        ]])
        try:
            await message.bot.send_message(
                recipient_tg, f"📨 Новое сообщение во встроенном чате VitalTrack",
                reply_markup=kb,
            )
        except Exception:
            pass
    await state.clear()
    await message.answer("Отправлено.", reply_markup=doctor_menu()
                         if user.role == UserRole.DOCTOR else None)


@router.callback_query(F.data == "doc:alerts")
async def doc_alerts(cq: CallbackQuery, session: AsyncSession, user: User) -> None:
    if user.role != UserRole.DOCTOR:
        await cq.answer("Только для врачей", show_alert=True); return
    patients = await UserService(session).list_patients_for(user)
    if not patients:
        await cq.message.edit_text("Нет пациентов.", reply_markup=doctor_menu())
        await cq.answer(); return
    lines = ["Открытые алёрты:"]
    repo = AlertRepository(session)
    any_alert = False
    for p in patients:
        alerts = await repo.open_for_user(p.id)
        if not alerts:
            continue
        any_alert = True
        lines.append(f"\n<b>{p.full_name or p.telegram_id}</b>")
        for a in alerts[:5]:
            lines.append(f"  ⚠ {a.summary} ({format_user_dt(a.created_at, user.timezone)})")
    if not any_alert:
        lines = ["Нет открытых алёртов."]
    await cq.message.edit_text("\n".join(lines), reply_markup=doctor_menu())
    await cq.answer()
