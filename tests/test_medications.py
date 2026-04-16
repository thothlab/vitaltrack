from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.domain.enums import MedScheduleType
from app.services.medications import MedicationService


def _med(med_id, schedule_type, schedule_data):
    return SimpleNamespace(
        id=med_id, schedule_type=schedule_type, schedule_data=schedule_data
    )


def test_expected_intakes_fixed_times_one_day():
    start = datetime(2026, 4, 16, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    med = _med(1, MedScheduleType.FIXED_TIMES, {"times": ["08:00", "20:00"]})
    out = MedicationService.expected_intakes([med], start, end, "UTC")
    assert len(out[1]) == 2
    assert out[1][0].hour == 8 and out[1][1].hour == 20


def test_expected_intakes_interval():
    start = datetime(2026, 4, 16, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    med = _med(2, MedScheduleType.EVERY_N_HOURS,
               {"interval_hours": 8, "anchor": "08:00"})
    out = MedicationService.expected_intakes([med], start, end, "UTC")
    # An every-8h schedule anchored at 08:00 fires at 00:00, 08:00, 16:00.
    assert len(out[2]) == 3
    assert {dt.hour for dt in out[2]} == {0, 8, 16}


def test_prn_returns_no_slots():
    med = _med(3, MedScheduleType.AS_NEEDED, {})
    start = datetime(2026, 4, 16, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    out = MedicationService.expected_intakes([med], start, end, "UTC")
    assert out[3] == []
