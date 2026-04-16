from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.utils.i18n import t


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("cancel"), callback_data="cancel")]
    ])


def back_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("back"), callback_data="back"),
            InlineKeyboardButton(text=t("cancel"), callback_data="cancel"),
        ]
    ])


def now_or_input_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("now"), callback_data="time:now")],
        [InlineKeyboardButton(text=t("cancel"), callback_data="cancel")],
    ])


def yes_no_kb(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("yes"), callback_data=f"{prefix}:yes"),
        InlineKeyboardButton(text=t("no"), callback_data=f"{prefix}:no"),
    ]])


def consent_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Согласен", callback_data="consent:yes"),
        InlineKeyboardButton(text="✖ Отказаться", callback_data="consent:no"),
    ]])


def skip_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("skip"), callback_data="skip"),
        InlineKeyboardButton(text=t("cancel"), callback_data="cancel"),
    ]])
