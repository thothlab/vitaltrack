from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.reports import ReportData
from app.utils.time import format_user_dt

# Register a Unicode font so Cyrillic renders properly on any platform.
try:
    pdfmetrics.registerFont(TTFont("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
    _FONT = "DejaVu"
except Exception:
    _FONT = "Helvetica"


_PERIOD_RU = {"7d": "7 дней", "30d": "месяц", "90d": "3 месяца", "custom": "период"}


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontName=_FONT, fontSize=16, spaceAfter=6
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName=_FONT, fontSize=13, spaceAfter=4
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontName=_FONT, fontSize=10, leading=13
        ),
    }


def render_pdf(data: ReportData) -> bytes:
    styles = _styles()
    tz = data.user.timezone
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.6 * cm, rightMargin=1.6 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title="VitalTrack report",
    )
    story: list = []
    story.append(Paragraph("VitalTrack — отчёт", styles["title"]))
    story.append(Paragraph(
        f"Период: {_PERIOD_RU.get(data.period.value, data.period.value)} "
        f"({format_user_dt(data.start, tz, '%d.%m.%Y')} — "
        f"{format_user_dt(data.end, tz, '%d.%m.%Y')})",
        styles["body"]
    ))
    if data.user.full_name:
        story.append(Paragraph(f"Пациент: {data.user.full_name}", styles["body"]))
    story.append(Spacer(1, 0.5 * cm))

    # Pressure
    story.append(Paragraph("Давление", styles["h2"]))
    ps = data.pressure
    if ps.n == 0:
        story.append(Paragraph("Нет данных", styles["body"]))
    else:
        tbl = Table([
            ["Измерений", ps.n],
            ["Среднее САД/ДАД", f"{ps.sys_mean}/{ps.dia_mean}"],
            ["Средняя ЧСС", ps.hr_mean or "—"],
            ["Макс. САД/ДАД", f"{ps.sys_max}/{ps.dia_max}"],
            ["Мин. САД/ДАД", f"{ps.sys_min}/{ps.dia_min}"],
            ["Эпизодов высокого", ps.high_count],
            ["Эпизодов низкого", ps.low_count],
        ], colWidths=[6 * cm, 8 * cm])
        tbl.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), _FONT, 10),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f4f4f4")),
        ]))
        story.append(tbl)
    story.append(Spacer(1, 0.3 * cm))

    # Glucose
    story.append(Paragraph("Глюкоза", styles["h2"]))
    gs = data.glucose
    if gs.n == 0:
        story.append(Paragraph("Нет данных", styles["body"]))
    else:
        tbl = Table([
            ["Измерений", gs.n],
            ["Среднее", gs.value_mean],
            ["Натощак (среднее)", gs.fasting_mean or "—"],
            ["После еды (среднее)", gs.post_meal_mean or "—"],
            ["Мин", gs.value_min],
            ["Макс", gs.value_max],
            ["Гипогликемии", gs.hypo_count],
            ["Гипергликемии", gs.hyper_count],
        ], colWidths=[6 * cm, 8 * cm])
        tbl.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), _FONT, 10),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f4f4f4")),
        ]))
        story.append(tbl)
    story.append(Spacer(1, 0.3 * cm))

    # Adherence
    story.append(Paragraph("Приём лекарств", styles["h2"]))
    if not data.adherence.by_med:
        story.append(Paragraph("Нет активных назначений", styles["body"]))
    else:
        rows = [["Препарат", "Плановых", "Принято", "Пропущено", "%"]]
        for _mid, row in data.adherence.by_med.items():
            med = row["medication"]
            rate_str = f"{round((row['rate'] or 0) * 100)}%" if row["expected"] else "PRN"
            rows.append([
                med.name, row["expected"], row["taken"], row["missed"], rate_str,
            ])
        tbl = Table(rows, colWidths=[6 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm, 2 * cm])
        tbl.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), _FONT, 10),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4f4f4")),
        ]))
        story.append(tbl)

    story.append(Spacer(1, 0.3 * cm))

    # Symptoms
    if data.symptoms:
        from collections import Counter
        story.append(Paragraph("Симптомы", styles["h2"]))
        c: Counter[str] = Counter()
        for s in data.symptoms:
            c.update(s.symptoms)
        rows = [["Симптом", "Раз"]]
        for k, v in c.most_common(10):
            rows.append([k, v])
        if len(rows) > 1:
            tbl = Table(rows, colWidths=[10 * cm, 4 * cm])
            tbl.setStyle(TableStyle([
                ("FONT", (0, 0), (-1, -1), _FONT, 10),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4f4f4")),
            ]))
            story.append(tbl)

    # Latest lab
    if data.latest_lab:
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("Последние анализы", styles["h2"]))
        l = data.latest_lab
        rows = [["Показатель", "Значение"], ["Дата", format_user_dt(l.drawn_at, tz, "%d.%m.%Y")]]
        for label, v in (
            ("ОХ, ммоль/л", l.total_chol),
            ("ЛПНП, ммоль/л", l.ldl),
            ("ЛПВП, ммоль/л", l.hdl),
            ("Триглицериды, ммоль/л", l.triglycerides),
            ("Глюкоза натощак, ммоль/л", l.glucose_fasting),
            ("Инсулин натощак, µU/mL", l.insulin_fasting),
            ("Креатинин, µмоль/л", l.creatinine_umol),
        ):
            if v is not None:
                rows.append([label, v])
        tbl = Table(rows, colWidths=[8 * cm, 6 * cm])
        tbl.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), _FONT, 10),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4f4f4")),
        ]))
        story.append(tbl)

    doc.build(story)
    return buf.getvalue()
