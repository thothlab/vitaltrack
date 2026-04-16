from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.utils.i18n import t


def main_menu(is_doctor: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=t("menu_record"), callback_data="menu:record")],
        [
            InlineKeyboardButton(text=t("menu_meds"), callback_data="menu:meds"),
            InlineKeyboardButton(text=t("menu_history"), callback_data="menu:history"),
        ],
        [
            InlineKeyboardButton(text=t("menu_reports"), callback_data="menu:reports"),
            InlineKeyboardButton(text=t("menu_calc"), callback_data="menu:calc"),
        ],
        [InlineKeyboardButton(text=t("menu_settings"), callback_data="menu:settings")],
    ]
    if is_doctor:
        rows.insert(
            0,
            [InlineKeyboardButton(text=t("menu_doctor"), callback_data="menu:doctor")],
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def record_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("rec_pressure"), callback_data="rec:pressure"),
            InlineKeyboardButton(text=t("rec_glucose"), callback_data="rec:glucose"),
        ],
        [
            InlineKeyboardButton(text=t("rec_med_intake"), callback_data="rec:med"),
            InlineKeyboardButton(text=t("rec_symptoms"), callback_data="rec:symptoms"),
        ],
        [
            InlineKeyboardButton(text=t("rec_meal"), callback_data="rec:meal"),
            InlineKeyboardButton(text=t("rec_lab"), callback_data="rec:lab"),
        ],
        [InlineKeyboardButton(text=t("back"), callback_data="menu:home")],
    ])


def history_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ АД", callback_data="hist:pressure"),
            InlineKeyboardButton(text="🩸 Сахар", callback_data="hist:glucose"),
        ],
        [
            InlineKeyboardButton(text="💊 Лекарства", callback_data="hist:meds"),
            InlineKeyboardButton(text="🤒 Симптомы", callback_data="hist:symptoms"),
        ],
        [InlineKeyboardButton(text=t("back"), callback_data="menu:home")],
    ])


def reports_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="7 дней", callback_data="rep:period:7d"),
            InlineKeyboardButton(text="Месяц", callback_data="rep:period:30d"),
        ],
        [
            InlineKeyboardButton(text="3 месяца", callback_data="rep:period:90d"),
            InlineKeyboardButton(text="Период…", callback_data="rep:period:custom"),
        ],
        [InlineKeyboardButton(text=t("back"), callback_data="menu:home")],
    ])


def report_format_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Текст", callback_data="rep:fmt:text"),
            InlineKeyboardButton(text="PDF", callback_data="rep:fmt:pdf"),
            InlineKeyboardButton(text="CSV (zip)", callback_data="rep:fmt:csv"),
        ],
        [InlineKeyboardButton(text=t("cancel"), callback_data="cancel")],
    ])


def calc_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="BMI", callback_data="calc:bmi"),
            InlineKeyboardButton(text="GFR", callback_data="calc:gfr"),
        ],
        [
            InlineKeyboardButton(text="HOMA-IR", callback_data="calc:homa"),
            InlineKeyboardButton(text="SCORE2", callback_data="calc:score"),
        ],
        [InlineKeyboardButton(text=t("back"), callback_data="menu:home")],
    ])


def settings_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Часовой пояс", callback_data="set:tz")],
        [InlineKeyboardButton(text="Профиль (пол/рост/вес)", callback_data="set:profile")],
        [InlineKeyboardButton(text="Привязать врача", callback_data="set:doctor")],
        [InlineKeyboardButton(text="Удалить мои данные", callback_data="set:forget")],
        [InlineKeyboardButton(text="Назад", callback_data="menu:home")],
    ])
