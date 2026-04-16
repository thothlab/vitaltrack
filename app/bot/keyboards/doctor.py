from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import MessageThread, User


def doctor_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пациенты", callback_data="doc:patients")],
        [InlineKeyboardButton(text="Сообщения", callback_data="doc:threads")],
        [InlineKeyboardButton(text="Алёрты", callback_data="doc:alerts")],
        [InlineKeyboardButton(text="Назад", callback_data="menu:home")],
    ])


def patients_kb(patients: list[User]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=p.full_name or p.username or str(p.telegram_id),
            callback_data=f"doc:patient:{p.id}",
        )]
        for p in patients
    ]
    rows.append([InlineKeyboardButton(text="Назад", callback_data="menu:doctor")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def patient_view_kb(patient_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Отчёт 7д",
                                 callback_data=f"doc:report:{patient_id}:7d"),
            InlineKeyboardButton(text="Отчёт 30д",
                                 callback_data=f"doc:report:{patient_id}:30d"),
        ],
        [InlineKeyboardButton(text="Написать", callback_data=f"doc:msg:{patient_id}")],
        [InlineKeyboardButton(text="Назад", callback_data="doc:patients")],
    ])


def threads_kb(threads: list[MessageThread], me_role_doctor: bool) -> InlineKeyboardMarkup:
    rows = []
    for th in threads:
        peer = th.patient if me_role_doctor else th.doctor
        label = peer.full_name or peer.username or str(peer.telegram_id) if peer else f"#{th.id}"
        rows.append([InlineKeyboardButton(
            text=label, callback_data=f"thread:open:{th.id}"
        )])
    rows.append([InlineKeyboardButton(text="Назад", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def thread_view_kb(thread_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ответить", callback_data=f"thread:reply:{thread_id}")],
        [InlineKeyboardButton(text="Назад", callback_data="doc:threads")],
    ])
