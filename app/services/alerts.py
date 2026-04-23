from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import GlucoseRecord, PressureRecord, User
from app.domain.enums import AlertKind, AlertSeverity
from app.repositories.alerts import AlertRepository
from app.repositories.glucose import GlucoseRepository
from app.repositories.medications import MedicationRepository
from app.repositories.pressure import PressureRepository
from app.utils.time import now_utc


class AlertService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AlertRepository(session)
        self.settings = get_settings()

    # -------- thresholds --------
    def _threshold(self, user: User, key: str) -> float:
        if user.alert_settings and key in user.alert_settings:
            return float(user.alert_settings[key])
        return float(getattr(self.settings, key.lower()))

    # -------- evaluators --------
    async def evaluate_pressure(self, user: User, rec: PressureRecord) -> Optional[dict[str, Any]]:
        sys_high = self._threshold(user, "ALERT_BP_SYS_HIGH")
        dia_high = self._threshold(user, "ALERT_BP_DIA_HIGH")
        sys_low = self._threshold(user, "ALERT_BP_SYS_LOW")
        dia_low = self._threshold(user, "ALERT_BP_DIA_LOW")
        if rec.systolic >= sys_high or rec.diastolic >= dia_high:
            ok = await self.repo.insert_idempotent(
                user_id=user.id,
                kind=AlertKind.BP_HIGH,
                severity=AlertSeverity.WARNING if rec.systolic < 180 else AlertSeverity.CRITICAL,
                summary=f"Высокое АД: {rec.systolic}/{rec.diastolic}",
                dedup_key=f"bp_high:{user.id}:{rec.id}",
                payload={"sys": rec.systolic, "dia": rec.diastolic, "record_id": rec.id},
            )
            if ok:
                return {"kind": AlertKind.BP_HIGH, "summary": f"Высокое АД: {rec.systolic}/{rec.diastolic}"}
        if rec.systolic <= sys_low or rec.diastolic <= dia_low:
            ok = await self.repo.insert_idempotent(
                user_id=user.id,
                kind=AlertKind.BP_LOW,
                severity=AlertSeverity.WARNING,
                summary=f"Низкое АД: {rec.systolic}/{rec.diastolic}",
                dedup_key=f"bp_low:{user.id}:{rec.id}",
                payload={"sys": rec.systolic, "dia": rec.diastolic, "record_id": rec.id},
            )
            if ok:
                return {"kind": AlertKind.BP_LOW, "summary": f"Низкое АД: {rec.systolic}/{rec.diastolic}"}
        return None

    async def evaluate_glucose(self, user: User, rec: GlucoseRecord) -> Optional[dict[str, Any]]:
        low = self._threshold(user, "ALERT_GLUCOSE_LOW")
        high = self._threshold(user, "ALERT_GLUCOSE_HIGH")
        if rec.value_mmol < low:
            sev = AlertSeverity.CRITICAL if rec.value_mmol < 3.0 else AlertSeverity.WARNING
            ok = await self.repo.insert_idempotent(
                user_id=user.id,
                kind=AlertKind.GLUCOSE_LOW,
                severity=sev,
                summary=f"Низкая глюкоза: {rec.value_mmol} ммоль/л",
                dedup_key=f"glu_low:{user.id}:{rec.id}",
                payload={"value": rec.value_mmol, "record_id": rec.id},
            )
            if ok:
                return {"kind": AlertKind.GLUCOSE_LOW, "summary": f"Низкая глюкоза: {rec.value_mmol}"}
        elif rec.value_mmol > high:
            sev = AlertSeverity.WARNING
            ok = await self.repo.insert_idempotent(
                user_id=user.id,
                kind=AlertKind.GLUCOSE_HIGH,
                severity=sev,
                summary=f"Высокая глюкоза: {rec.value_mmol} ммоль/л",
                dedup_key=f"glu_high:{user.id}:{rec.id}",
                payload={"value": rec.value_mmol, "record_id": rec.id},
            )
            if ok:
                return {"kind": AlertKind.GLUCOSE_HIGH, "summary": f"Высокая глюкоза: {rec.value_mmol}"}
        return None

    async def detect_no_data(self, user: User) -> Optional[dict[str, Any]]:
        days = int(self._threshold(user, "ALERT_NO_DATA_DAYS"))
        cutoff = now_utc() - timedelta(days=days)
        last_p = await PressureRepository(self.session).latest_one(user.id)
        last_g = await GlucoseRepository(self.session).latest_one(user.id)
        last_dt = max(
            (r.measured_at for r in (last_p, last_g) if r is not None),
            default=None,
        )
        if last_dt is None or last_dt < cutoff:
            day_key = now_utc().date().isoformat()
            ok = await self.repo.insert_idempotent(
                user_id=user.id,
                kind=AlertKind.NO_DATA,
                severity=AlertSeverity.INFO,
                summary=f"Нет измерений более {days} дн.",
                dedup_key=f"no_data:{user.id}:{day_key}",
                payload={"last_measure_at": last_dt.isoformat() if last_dt else None},
            )
            if ok:
                return {"kind": AlertKind.NO_DATA, "summary": f"Нет измерений более {days} дн."}
        return None

    async def detect_missed_meds(self, user: User) -> list[dict[str, Any]]:
        hours = int(self._threshold(user, "ALERT_MISSED_MED_HOURS"))
        now = now_utc()
        window_start = now - timedelta(hours=24)
        med_repo = MedicationRepository(self.session)
        meds = await med_repo.list_active(user.id)
        from app.services.medications import MedicationService
        expected = MedicationService.expected_intakes(meds, window_start, now, user.timezone)
        intakes = await med_repo.intakes_between(user.id, window_start, now)
        taken_keys = {(ix.medication_id, ix.scheduled_at) for ix in intakes if ix.taken}

        results: list[dict[str, Any]] = []
        for med in meds:
            for slot in expected.get(med.id, []):
                if (now - slot) < timedelta(hours=hours):
                    continue
                if (med.id, slot) in taken_keys:
                    continue
                ok = await self.repo.insert_idempotent(
                    user_id=user.id,
                    kind=AlertKind.MED_MISSED,
                    severity=AlertSeverity.WARNING,
                    summary=f"Пропуск приёма «{med.name}» в {slot.isoformat()}",
                    dedup_key=f"med_missed:{user.id}:{med.id}:{slot.isoformat()}",
                    payload={"medication_id": med.id, "scheduled_at": slot.isoformat()},
                )
                if ok:
                    await med_repo.record_missed(
                        user_id=user.id,
                        medication_id=med.id,
                        scheduled_at=slot,
                    )
                    results.append(
                        {
                            "kind": AlertKind.MED_MISSED,
                            "medication_id": med.id,
                            "scheduled_at": slot,
                            "summary": f"Пропуск приёма «{med.name}»",
                        }
                    )
        return results

    async def acknowledge(self, alert_id: int, by_user: User) -> None:
        alert = await self.repo.by_id(alert_id)
        if alert is None:
            return
        await self.repo.acknowledge(alert, by_user.id, now_utc())
