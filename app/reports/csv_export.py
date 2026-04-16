from __future__ import annotations

import csv
import io
import zipfile

from app.services.reports import ReportData
from app.utils.time import format_user_dt


def _csv_bytes(rows: list[list]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, dialect="excel")
    for r in rows:
        w.writerow(r)
    return buf.getvalue().encode("utf-8-sig")


def render_csv_bundle(data: ReportData) -> bytes:
    """Return a ZIP bundle with 4 CSVs: pressure, glucose, meds, symptoms."""
    tz = data.user.timezone
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as zf:
        rows = [["measured_at", "systolic", "diastolic", "pulse", "arm", "note"]]
        for r in data.pressure_records:
            rows.append([
                format_user_dt(r.measured_at, tz, "%Y-%m-%d %H:%M"),
                r.systolic, r.diastolic, r.pulse or "", r.arm or "", r.note or "",
            ])
        zf.writestr("pressure.csv", _csv_bytes(rows))

        rows = [["measured_at", "value_mmol", "context", "note"]]
        for r in data.glucose_records:
            rows.append([
                format_user_dt(r.measured_at, tz, "%Y-%m-%d %H:%M"),
                r.value_mmol, r.context.value, r.note or "",
            ])
        zf.writestr("glucose.csv", _csv_bytes(rows))

        rows = [["medication", "expected", "taken", "missed", "rate"]]
        for _mid, row in data.adherence.by_med.items():
            med = row["medication"]
            rows.append([
                med.name, row["expected"], row["taken"],
                row["missed"], row["rate"] if row["rate"] is not None else "",
            ])
        zf.writestr("medications.csv", _csv_bytes(rows))

        rows = [["occurred_at", "wellbeing", "intensity", "symptoms", "note"]]
        for s in data.symptoms:
            rows.append([
                format_user_dt(s.occurred_at, tz, "%Y-%m-%d %H:%M"),
                s.wellbeing.value, s.intensity or "",
                ";".join(s.symptoms), s.note or "",
            ])
        zf.writestr("symptoms.csv", _csv_bytes(rows))

    return zbuf.getvalue()
