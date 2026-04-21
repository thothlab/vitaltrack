from __future__ import annotations

from datetime import datetime

from app.services.reports import ReportData
from app.utils.time import format_user_dt

_PERIOD_RU = {"7d": "7 дней", "30d": "месяц", "90d": "3 месяца", "custom": "период"}


def render_text(data: ReportData) -> str:
    u = data.user
    tz = u.timezone
    parts: list[str] = []
    parts.append(f"📋 Отчёт за {_PERIOD_RU.get(data.period.value, data.period.value)}")
    parts.append(
        f"{format_user_dt(data.start, tz, '%d.%m.%Y')} — "
        f"{format_user_dt(data.end, tz, '%d.%m.%Y')}"
    )
    parts.append("")

    # Pressure
    parts.append("❤️ Давление")
    ps = data.pressure
    if ps.n == 0:
        parts.append("  нет данных")
    else:
        parts.append(f"  измерений: {ps.n}")
        parts.append(f"  среднее: {ps.sys_mean}/{ps.dia_mean}"
                     + (f", ЧСС {ps.hr_mean}" if ps.hr_mean else ""))
        parts.append(f"  макс: {ps.sys_max}/{ps.dia_max}, мин: {ps.sys_min}/{ps.dia_min}")
        parts.append(f"  эпизодов выше порога: {ps.high_count}, ниже: {ps.low_count}")
        if len(data.pressure_daily) > 1:
            parts.append("  По дням:")
            for row in data.pressure_daily:
                label = datetime.strptime(row.date, "%Y-%m-%d").strftime("%d.%m")
                line = f"    {label}: ср {row.sys_mean}/{row.dia_mean}"
                if row.hr_mean is not None:
                    line += f", ЧСС {row.hr_mean}"
                line += f" (×{row.n})"
                parts.append(line)
                parts.append(
                    f"         макс {row.sys_max}/{row.dia_max},"
                    f" мин {row.sys_min}/{row.dia_min}"
                )
    parts.append("")

    # Glucose
    parts.append("🩸 Сахар")
    gs = data.glucose
    if gs.n == 0:
        parts.append("  нет данных")
    else:
        parts.append(f"  измерений: {gs.n}")
        parts.append(f"  среднее: {gs.value_mean} ммоль/л")
        if gs.fasting_mean is not None:
            parts.append(f"  натощак: {gs.fasting_mean}")
        if gs.post_meal_mean is not None:
            parts.append(f"  после еды: {gs.post_meal_mean}")
        parts.append(
            f"  эпизодов низкой: {gs.hypo_count}, высокой: {gs.hyper_count}"
        )
    parts.append("")

    # Adherence
    parts.append("💊 Приём лекарств")
    adh = data.adherence
    if not adh.by_med:
        parts.append("  нет активных назначений")
    else:
        if adh.overall_rate is not None:
            parts.append(f"  общий adherence: {round(adh.overall_rate * 100)}%")
        for med_id, row in adh.by_med.items():
            med = row["medication"]
            if row["expected"]:
                rate = round((row["rate"] or 0) * 100)
                parts.append(
                    f"  {med.name}: {row['taken']}/{row['expected']} ({rate}%)"
                )
            else:
                parts.append(f"  {med.name}: по требованию")
    parts.append("")

    # Symptoms
    parts.append("🤒 Симптомы")
    if not data.symptoms:
        parts.append("  нет записей")
    else:
        parts.append(f"  записей: {len(data.symptoms)}")
        # Top 3 symptoms
        from collections import Counter
        c: Counter[str] = Counter()
        for s in data.symptoms:
            c.update(s.symptoms)
        if c:
            top = ", ".join(f"{k} ×{v}" for k, v in c.most_common(3))
            parts.append(f"  частые: {top}")
    parts.append("")

    # Latest lab
    if data.latest_lab:
        parts.append("🧪 Последние анализы")
        l = data.latest_lab
        parts.append(f"  дата: {format_user_dt(l.drawn_at, tz, '%d.%m.%Y')}")
        bits = []
        for label, v in (
            ("ОХ", l.total_chol), ("ЛПНП", l.ldl), ("ЛПВП", l.hdl),
            ("ТГ", l.triglycerides), ("Глк", l.glucose_fasting),
        ):
            if v is not None:
                bits.append(f"{label}={v}")
        if bits:
            parts.append("  " + ", ".join(bits))
        parts.append("")

    return "\n".join(parts).rstrip()
