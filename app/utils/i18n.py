"""Tiny RU-only string registry. The whole bot UI is in Russian per the spec."""
from __future__ import annotations

STR = {
    "menu_record": "📝 Записать",
    "menu_history": "📈 История",
    "menu_reports": "📄 Отчёты",
    "menu_meds": "💊 Лекарства",
    "menu_calc": "🧮 Калькуляторы",
    "menu_doctor": "🩺 Врач",
    "menu_settings": "⚙️ Настройки",

    "rec_pressure": "❤️ Давление",
    "rec_glucose": "🩸 Сахар",
    "rec_symptoms": "🤒 Симптомы",
    "rec_meal": "🍽 Питание",
    "rec_lab": "🧪 Анализы",
    "rec_med_intake": "💊 Принял лекарство",

    "back": "‹ Назад",
    "cancel": "✖ Отмена",
    "skip": "Пропустить",
    "done": "Готово",
    "yes": "Да",
    "no": "Нет",
    "now": "Сейчас",

    "consent_request": (
        "Перед началом работы мне нужно ваше согласие на хранение медицинских "
        "данных в этом сервисе. Данные хранятся только для вас и (при подключении) "
        "вашего лечащего врача. Вы можете удалить их в любой момент командой "
        "/forget_me."
    ),
    "consent_granted": "Спасибо, согласие сохранено. Можно начинать.",

    "ask_time": (
        "Когда было измерение?\n"
        "Можно выбрать «Сейчас» или ввести: HH:MM, «вчера 21:30», 02.04 09:15"
    ),
}


def t(key: str) -> str:
    return STR.get(key, key)
