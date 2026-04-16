from __future__ import annotations

from datetime import datetime, date
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampedMixin
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


def _pgenum(enum_cls, name: str) -> SAEnum:
    """Postgres ENUM bound to the .value (lowercase) of each member, not the
    Python member NAME. Without values_callable SQLAlchemy would send
    'PATIENT' instead of 'patient' and Postgres would reject it."""
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda c: [m.value for m in c],
        native_enum=True,
        create_type=False,
    )


# --------------------------------------------------------------------- USERS
class User(Base, TimestampedMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(64))
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        _pgenum(UserRole, "user_role"), default=UserRole.PATIENT, nullable=False
    )
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow", nullable=False)
    locale: Mapped[str] = mapped_column(String(8), default="ru", nullable=False)

    # Patient profile
    sex: Mapped[Optional[Sex]] = mapped_column(_pgenum(Sex, "sex"))
    birth_date: Mapped[Optional[date]] = mapped_column(Date)
    height_cm: Mapped[Optional[float]] = mapped_column(Float)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    is_smoker: Mapped[Optional[bool]] = mapped_column(Boolean)
    has_diabetes: Mapped[Optional[bool]] = mapped_column(Boolean)

    # Consent / lifecycle
    consent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Per-user override of alert thresholds
    alert_settings: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)

    # Doctor ↔ patient linkage (a patient may belong to one doctor)
    doctor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    doctor = relationship("User", remote_side="User.id", foreign_keys=[doctor_id])

    pressure_records = relationship(
        "PressureRecord", back_populates="user", cascade="all, delete-orphan"
    )
    glucose_records = relationship(
        "GlucoseRecord", back_populates="user", cascade="all, delete-orphan"
    )
    medications = relationship(
        "Medication", back_populates="user", cascade="all, delete-orphan"
    )
    intakes = relationship(
        "MedicationIntake", back_populates="user", cascade="all, delete-orphan"
    )
    symptoms = relationship(
        "SymptomRecord", back_populates="user", cascade="all, delete-orphan"
    )
    meals = relationship("MealRecord", back_populates="user", cascade="all, delete-orphan")
    labs = relationship("LabResult", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship(
        "Alert",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Alert.user_id",
    )


# ----------------------------------------------------------------- PRESSURE
class PressureRecord(Base, TimestampedMixin):
    """Single BP measurement. Multiple measurements can share session_uuid
    when the user takes 2-3 readings in a row."""

    __tablename__ = "pressure_records"
    __table_args__ = (
        Index("ix_pressure_user_time", "user_id", "measured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    systolic: Mapped[int] = mapped_column(Integer, nullable=False)
    diastolic: Mapped[int] = mapped_column(Integer, nullable=False)
    pulse: Mapped[Optional[int]] = mapped_column(Integer)
    arm: Mapped[Optional[str]] = mapped_column(String(8))  # left|right
    session_uuid: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    note: Mapped[Optional[str]] = mapped_column(Text)

    user = relationship("User", back_populates="pressure_records")


# ------------------------------------------------------------------ GLUCOSE
class GlucoseRecord(Base, TimestampedMixin):
    __tablename__ = "glucose_records"
    __table_args__ = (
        Index("ix_glucose_user_time", "user_id", "measured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value_mmol: Mapped[float] = mapped_column(Float, nullable=False)
    context: Mapped[GlucoseContext] = mapped_column(
        _pgenum(GlucoseContext, "glucose_context"), nullable=False
    )
    note: Mapped[Optional[str]] = mapped_column(Text)

    user = relationship("User", back_populates="glucose_records")


# -------------------------------------------------------------- MEDICATIONS
class Medication(Base, TimestampedMixin):
    __tablename__ = "medications"
    __table_args__ = (
        Index("ix_meds_user_active", "user_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dose: Mapped[Optional[str]] = mapped_column(String(64))     # "5 mg", "1 tab"
    notes: Mapped[Optional[str]] = mapped_column(Text)

    schedule_type: Mapped[MedScheduleType] = mapped_column(
        _pgenum(MedScheduleType, "med_schedule_type"), nullable=False
    )
    # FIXED_TIMES: {"times": ["08:00", "20:00"]}
    # EVERY_N_HOURS: {"interval_hours": 8, "anchor": "08:00"}
    schedule_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    starts_on: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    ends_on: Mapped[Optional[date]] = mapped_column(Date)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="medications")
    intakes = relationship(
        "MedicationIntake", back_populates="medication", cascade="all, delete-orphan"
    )


class MedicationIntake(Base, TimestampedMixin):
    """Either a logged intake (taken=True) or a missed-dose marker (taken=False).

    `scheduled_at` is set for adherence tracking; if user just logs an intake
    ad-hoc it is None and we don't count it in adherence.
    """

    __tablename__ = "medication_intakes"
    __table_args__ = (
        UniqueConstraint(
            "medication_id", "scheduled_at",
            name="uq_intake_med_scheduled",
        ),
        Index("ix_intake_user_time", "user_id", "taken_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    medication_id: Mapped[int] = mapped_column(
        ForeignKey("medications.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    taken_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    taken: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)

    user = relationship("User", back_populates="intakes")
    medication = relationship("Medication", back_populates="intakes")


# ---------------------------------------------------------------- SYMPTOMS
class SymptomRecord(Base, TimestampedMixin):
    __tablename__ = "symptom_records"
    __table_args__ = (
        Index("ix_symptom_user_time", "user_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    wellbeing: Mapped[WellbeingGrade] = mapped_column(
        _pgenum(WellbeingGrade, "wellbeing_grade"), nullable=False
    )
    symptoms: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    intensity: Mapped[Optional[int]] = mapped_column(Integer)  # 1..10
    note: Mapped[Optional[str]] = mapped_column(Text)

    user = relationship("User", back_populates="symptoms")


# --------------------------------------------------------------- NUTRITION
class MealRecord(Base, TimestampedMixin):
    __tablename__ = "meal_records"
    __table_args__ = (
        Index("ix_meal_user_time", "user_id", "eaten_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    eaten_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    meal_type: Mapped[MealType] = mapped_column(_pgenum(MealType, "meal_type"), nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    note: Mapped[Optional[str]] = mapped_column(Text)

    user = relationship("User", back_populates="meals")


# -------------------------------------------------------------------- LABS
class LabResult(Base, TimestampedMixin):
    __tablename__ = "lab_results"
    __table_args__ = (
        Index("ix_lab_user_time", "user_id", "drawn_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    drawn_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_chol: Mapped[Optional[float]] = mapped_column(Float)   # mmol/L
    ldl: Mapped[Optional[float]] = mapped_column(Float)
    hdl: Mapped[Optional[float]] = mapped_column(Float)
    triglycerides: Mapped[Optional[float]] = mapped_column(Float)
    glucose_fasting: Mapped[Optional[float]] = mapped_column(Float)
    insulin_fasting: Mapped[Optional[float]] = mapped_column(Float)  # µU/mL
    creatinine_umol: Mapped[Optional[float]] = mapped_column(Float)
    extra: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    note: Mapped[Optional[str]] = mapped_column(Text)

    user = relationship("User", back_populates="labs")


# ------------------------------------------------------------------ ALERTS
class Alert(Base, TimestampedMixin):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_user_kind_time", "user_id", "kind", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[AlertKind] = mapped_column(_pgenum(AlertKind, "alert_kind"), nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(
        _pgenum(AlertSeverity, "alert_severity"), nullable=False
    )
    summary: Mapped[str] = mapped_column(String(512), nullable=False)
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    acknowledged_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # Idempotency key (kind + day + extra) so periodic jobs don't duplicate
    dedup_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    user = relationship("User", back_populates="alerts", foreign_keys=[user_id])


# ------------------------------------------------------- DOCTOR ↔ PATIENT MSG
class MessageThread(Base, TimestampedMixin):
    """One thread per (doctor, patient) pair."""

    __tablename__ = "message_threads"
    __table_args__ = (
        UniqueConstraint("doctor_id", "patient_id", name="uq_thread_doctor_patient"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    doctor = relationship("User", foreign_keys=[doctor_id])
    patient = relationship("User", foreign_keys=[patient_id])
    messages = relationship(
        "Message", back_populates="thread", cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base, TimestampedMixin):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_thread_time", "thread_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("message_threads.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    thread = relationship("MessageThread", back_populates="messages")
    sender = relationship("User")


# -------------------------------------------------------------- REMINDERS
class Reminder(Base, TimestampedMixin):
    """Persisted reminder configuration. Actual schedule is mirrored in the
    APScheduler jobstore; this table is the source of truth for reconciling
    after restarts."""

    __tablename__ = "reminders"
    __table_args__ = (
        Index("ix_rem_user_kind", "user_id", "kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # bp|glucose|med
    medication_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("medications.id", ondelete="CASCADE")
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
