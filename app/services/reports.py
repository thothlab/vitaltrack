from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import mean
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    GlucoseRecord,
    LabResult,
    MealRecord,
    PressureRecord,
    SymptomRecord,
    User,
)
from app.domain.enums import ReportPeriod
from app.repositories.glucose import GlucoseRepository
from app.repositories.labs import LabRepository
from app.repositories.medications import MedicationRepository
from app.repositories.nutrition import NutritionRepository
from app.repositories.pressure import PressureRepository
from app.repositories.symptoms import SymptomRepository
from app.services.medications import MedicationService
from app.utils.time import now_utc, to_user_tz


@dataclass
class PressureSummary:
    n: int = 0
    sys_mean: Optional[float] = None
    dia_mean: Optional[float] = None
    hr_mean: Optional[float] = None
    sys_max: Optional[int] = None
    dia_max: Optional[int] = None
    sys_min: Optional[int] = None
    dia_min: Optional[int] = None
    high_count: int = 0
    low_count: int = 0


@dataclass
class GlucoseSummary:
    n: int = 0
    value_mean: Optional[float] = None
    value_max: Optional[float] = None
    value_min: Optional[float] = None
    fasting_mean: Optional[float] = None
    post_meal_mean: Optional[float] = None
    hypo_count: int = 0
    hyper_count: int = 0


@dataclass
class AdherenceSummary:
    by_med: dict[int, dict] = field(default_factory=dict)
    overall_rate: Optional[float] = None


@dataclass
class PressureDailyRow:
    date: str           # YYYY-MM-DD in user's timezone
    n: int
    sys_mean: float
    dia_mean: float
    hr_mean: Optional[float]
    sys_max: int
    dia_max: int
    sys_min: int
    dia_min: int


@dataclass
class ReportData:
    user: User
    period: ReportPeriod
    start: datetime
    end: datetime
    pressure: PressureSummary
    glucose: GlucoseSummary
    adherence: AdherenceSummary
    pressure_records: list[PressureRecord]
    glucose_records: list[GlucoseRecord]
    symptoms: list[SymptomRecord]
    meals: list[MealRecord]
    latest_lab: Optional[LabResult]
    pressure_daily: list[PressureDailyRow] = field(default_factory=list)


PERIOD_DAYS = {
    ReportPeriod.WEEK: 7,
    ReportPeriod.MONTH: 30,
    ReportPeriod.QUARTER: 90,
}


def period_window(period: ReportPeriod, custom_start: Optional[datetime] = None,
                  custom_end: Optional[datetime] = None) -> tuple[datetime, datetime]:
    end = now_utc()
    if period == ReportPeriod.CUSTOM:
        if custom_start is None or custom_end is None:
            raise ValueError("custom period requires start and end")
        return custom_start, custom_end
    return end - timedelta(days=PERIOD_DAYS[period]), end


class ReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def aggregate(
        self,
        user: User,
        period: ReportPeriod,
        custom_start: Optional[datetime] = None,
        custom_end: Optional[datetime] = None,
    ) -> ReportData:
        from app.services.alerts import AlertService

        start, end = period_window(period, custom_start, custom_end)

        pressure = await PressureRepository(self.session).list_between(user.id, start, end)
        glucose = await GlucoseRepository(self.session).list_between(user.id, start, end)
        symptoms = await SymptomRepository(self.session).list_between(user.id, start, end)
        meals = await NutritionRepository(self.session).list_between(user.id, start, end)
        latest_lab = await LabRepository(self.session).latest(user.id)

        # Pressure summary
        ps = PressureSummary()
        pressure_daily: list[PressureDailyRow] = []
        if pressure:
            ps.n = len(pressure)
            ps.sys_mean = round(mean(r.systolic for r in pressure), 1)
            ps.dia_mean = round(mean(r.diastolic for r in pressure), 1)
            hrs = [r.pulse for r in pressure if r.pulse is not None]
            ps.hr_mean = round(mean(hrs), 1) if hrs else None
            ps.sys_max = max(r.systolic for r in pressure)
            ps.dia_max = max(r.diastolic for r in pressure)
            ps.sys_min = min(r.systolic for r in pressure)
            ps.dia_min = min(r.diastolic for r in pressure)
            asvc = AlertService(self.session)
            sys_high = asvc._threshold(user, "ALERT_BP_SYS_HIGH")
            dia_high = asvc._threshold(user, "ALERT_BP_DIA_HIGH")
            sys_low = asvc._threshold(user, "ALERT_BP_SYS_LOW")
            dia_low = asvc._threshold(user, "ALERT_BP_DIA_LOW")
            ps.high_count = sum(
                1 for r in pressure if r.systolic >= sys_high or r.diastolic >= dia_high
            )
            ps.low_count = sum(
                1 for r in pressure if r.systolic <= sys_low or r.diastolic <= dia_low
            )

            # Per-day averages (grouped in user's local timezone)
            by_day: dict[str, list] = defaultdict(list)
            for r in pressure:
                day_key = to_user_tz(r.measured_at, user.timezone).strftime("%Y-%m-%d")
                by_day[day_key].append(r)
            for day in sorted(by_day):
                recs = by_day[day]
                day_hrs = [r.pulse for r in recs if r.pulse is not None]
                pressure_daily.append(PressureDailyRow(
                    date=day,
                    n=len(recs),
                    sys_mean=round(mean(r.systolic for r in recs), 1),
                    dia_mean=round(mean(r.diastolic for r in recs), 1),
                    hr_mean=round(mean(day_hrs), 1) if day_hrs else None,
                    sys_max=max(r.systolic for r in recs),
                    dia_max=max(r.diastolic for r in recs),
                    sys_min=min(r.systolic for r in recs),
                    dia_min=min(r.diastolic for r in recs),
                ))

        # Glucose summary
        gs = GlucoseSummary()
        if glucose:
            from app.domain.enums import GlucoseContext as GC
            gs.n = len(glucose)
            gs.value_mean = round(mean(r.value_mmol for r in glucose), 2)
            gs.value_max = max(r.value_mmol for r in glucose)
            gs.value_min = min(r.value_mmol for r in glucose)
            fasting = [r.value_mmol for r in glucose if r.context == GC.FASTING]
            post = [r.value_mmol for r in glucose if r.context == GC.POST_MEAL]
            gs.fasting_mean = round(mean(fasting), 2) if fasting else None
            gs.post_meal_mean = round(mean(post), 2) if post else None
            asvc = AlertService(self.session)
            low = asvc._threshold(user, "ALERT_GLUCOSE_LOW")
            high = asvc._threshold(user, "ALERT_GLUCOSE_HIGH")
            gs.hypo_count = sum(1 for r in glucose if r.value_mmol < low)
            gs.hyper_count = sum(1 for r in glucose if r.value_mmol > high)

        # Adherence
        med_service = MedicationService(self.session)
        per_med = await med_service.adherence(user, start, end)
        adh = AdherenceSummary(by_med=per_med)
        rates = [v["rate"] for v in per_med.values() if v["rate"] is not None]
        adh.overall_rate = round(mean(rates), 3) if rates else None

        return ReportData(
            user=user,
            period=period,
            start=start,
            end=end,
            pressure=ps,
            glucose=gs,
            adherence=adh,
            pressure_records=pressure,
            glucose_records=glucose,
            symptoms=symptoms,
            meals=meals,
            latest_lab=latest_lab,
            pressure_daily=pressure_daily,
        )
