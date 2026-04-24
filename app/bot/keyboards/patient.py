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
        [
            InlineKeyboardButton(text=t("rec_gi"), callback_data="rec:gi"),
            InlineKeyboardButton(text=t("rec_headache"), callback_data="rec:headache"),
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
        [
            InlineKeyboardButton(text="🫃 ЖКТ", callback_data="hist:gi"),
            InlineKeyboardButton(text="🤕 Голова", callback_data="hist:headache"),
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
        [InlineKeyboardButton(text="❤️ Риск ССЗ · SCORE2", callback_data="calc:score")],
        [InlineKeyboardButton(text="⚖️ ИМТ / BMI", callback_data="calc:bmi")],
        [InlineKeyboardButton(text="🧫 СКФ / eGFR", callback_data="calc:gfr")],
        [InlineKeyboardButton(text="🩸 Инсулинорезистентность · HOMA-IR", callback_data="calc:homa")],
        [InlineKeyboardButton(text=t("back"), callback_data="menu:home")],
    ])


def profile_menu() -> InlineKeyboardMarkup:
    """Per-field edit + full wizard. Each callback re-enters the profile
    handler, which re-renders the summary on completion."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пол", callback_data="prof:edit:sex")],
        [InlineKeyboardButton(text="Дата рождения", callback_data="prof:edit:birth")],
        [
            InlineKeyboardButton(text="Рост", callback_data="prof:edit:height"),
            InlineKeyboardButton(text="Вес", callback_data="prof:edit:weight"),
        ],
        [
            InlineKeyboardButton(text="Курение", callback_data="prof:edit:smoker"),
            InlineKeyboardButton(text="Диабет", callback_data="prof:edit:diabetes"),
        ],
        [InlineKeyboardButton(text="🪄 Заполнить целиком", callback_data="prof:wizard")],
        [InlineKeyboardButton(text=t("back"), callback_data="menu:settings")],
    ])


def settings_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Часовой пояс", callback_data="set:tz")],
        [InlineKeyboardButton(text="Профиль (пол/рост/вес)", callback_data="set:profile")],
        [InlineKeyboardButton(text="Привязать врача", callback_data="set:doctor")],
        [InlineKeyboardButton(text="Удалить мои данные", callback_data="set:forget")],
        [InlineKeyboardButton(text="Назад", callback_data="menu:home")],
    ])
