from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.domain.enums import (
    AlertKind,
    AlertSeverity,
    GlucoseContext,
    MealType,
    MedScheduleType,
    Sex,
    UserRole,
    WellbeingGrade,
)


# ---------------- USERS ----------------
class UserOut(BaseModel):
    id: int
    telegram_id: int
    full_name: Optional[str] = None
    role: UserRole
    timezone: str
    sex: Optional[Sex] = None
    birth_date: Optional[date] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    is_smoker: Optional[bool] = None
    has_diabetes: Optional[bool] = None
    consent_at: Optional[datetime] = None
    doctor_id: Optional[int] = None

    model_config = {"from_attributes": True}


# ---------------- PRESSURE -------------
class PressureIn(BaseModel):
    measured_at: datetime
    systolic: int = Field(ge=40, le=300)
    diastolic: int = Field(ge=20, le=250)
    pulse: Optional[int] = Field(default=None, ge=20, le=250)
    arm: Optional[str] = None
    session_uuid: Optional[str] = None
    note: Optional[str] = None


class PressureOut(PressureIn):
    id: int
    model_config = {"from_attributes": True}


# ---------------- GLUCOSE --------------
class GlucoseIn(BaseModel):
    measured_at: datetime
    value_mmol: float = Field(gt=0, lt=60)
    context: GlucoseContext
    note: Optional[str] = None


class GlucoseOut(GlucoseIn):
    id: int
    model_config = {"from_attributes": True}


# ---------------- MEDICATIONS ----------
class MedicationIn(BaseModel):
    name: str
    dose: Optional[str] = None
    notes: Optional[str] = None
    schedule_type: MedScheduleType
    schedule_data: dict[str, Any] = Field(default_factory=dict)
    starts_on: Optional[date] = None
    ends_on: Optional[date] = None


class MedicationOut(MedicationIn):
    id: int
    is_active: bool
    model_config = {"from_attributes": True}


class IntakeIn(BaseModel):
    medication_id: int
    scheduled_at: Optional[datetime] = None
    taken_at: Optional[datetime] = None
    taken: bool = True
    note: Optional[str] = None


# ---------------- SYMPTOMS -------------
class SymptomIn(BaseModel):
    occurred_at: datetime
    wellbeing: WellbeingGrade
    symptoms: list[str] = Field(default_factory=list)
    intensity: Optional[int] = Field(default=None, ge=1, le=10)
    note: Optional[str] = None


# ---------------- NUTRITION ------------
class MealIn(BaseModel):
    eaten_at: datetime
    meal_type: MealType
    tags: list[str] = Field(default_factory=list)
    note: Optional[str] = None


# ---------------- LABS -----------------
class LabIn(BaseModel):
    drawn_at: datetime
    total_chol: Optional[float] = None
    ldl: Optional[float] = None
    hdl: Optional[float] = None
    triglycerides: Optional[float] = None
    glucose_fasting: Optional[float] = None
    insulin_fasting: Optional[float] = None
    creatinine_umol: Optional[float] = None
    note: Optional[str] = None


# ---------------- ALERTS ---------------
class AlertOut(BaseModel):
    id: int
    kind: AlertKind
    severity: AlertSeverity
    summary: str
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    payload: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}
