"""Initial schema.

Revision ID: 0001_init
Revises:
Create Date: 2026-04-16

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


user_role = postgresql.ENUM("patient", "doctor", name="user_role", create_type=False)
sex = postgresql.ENUM("male", "female", name="sex", create_type=False)
glucose_context = postgresql.ENUM(
    "fasting", "before_meal", "post_meal", "bedtime", "random",
    name="glucose_context", create_type=False,
)
meal_type = postgresql.ENUM(
    "breakfast", "lunch", "dinner", "snack", name="meal_type", create_type=False,
)
wellbeing_grade = postgresql.ENUM(
    "great", "good", "ok", "poor", "bad",
    name="wellbeing_grade", create_type=False,
)
med_schedule_type = postgresql.ENUM(
    "fixed_times", "every_n_hours", "as_needed",
    name="med_schedule_type", create_type=False,
)
alert_kind = postgresql.ENUM(
    "bp_high", "bp_low", "glucose_high", "glucose_low", "med_missed", "no_data",
    name="alert_kind", create_type=False,
)
alert_severity = postgresql.ENUM(
    "info", "warning", "critical", name="alert_severity", create_type=False,
)


_ALL_ENUMS = (
    ("user_role", ("patient", "doctor")),
    ("sex", ("male", "female")),
    ("glucose_context", ("fasting", "before_meal", "post_meal", "bedtime", "random")),
    ("meal_type", ("breakfast", "lunch", "dinner", "snack")),
    ("wellbeing_grade", ("great", "good", "ok", "poor", "bad")),
    ("med_schedule_type", ("fixed_times", "every_n_hours", "as_needed")),
    ("alert_kind", ("bp_high", "bp_low", "glucose_high", "glucose_low", "med_missed", "no_data")),
    ("alert_severity", ("info", "warning", "critical")),
)


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in _ALL_ENUMS:
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("telegram_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("username", sa.String(64)),
        sa.Column("full_name", sa.String(255)),
        sa.Column("role", user_role, nullable=False, server_default="patient"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Europe/Moscow"),
        sa.Column("locale", sa.String(8), nullable=False, server_default="ru"),
        sa.Column("sex", sex),
        sa.Column("birth_date", sa.Date),
        sa.Column("height_cm", sa.Float),
        sa.Column("weight_kg", sa.Float),
        sa.Column("is_smoker", sa.Boolean),
        sa.Column("has_diabetes", sa.Boolean),
        sa.Column("consent_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("alert_settings", postgresql.JSONB),
        sa.Column("doctor_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)
    op.create_index("ix_users_doctor_id", "users", ["doctor_id"])

    op.create_table(
        "pressure_records",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("systolic", sa.Integer, nullable=False),
        sa.Column("diastolic", sa.Integer, nullable=False),
        sa.Column("pulse", sa.Integer),
        sa.Column("arm", sa.String(8)),
        sa.Column("session_uuid", sa.String(36)),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_pressure_user_time", "pressure_records", ["user_id", "measured_at"])
    op.create_index("ix_pressure_records_session_uuid", "pressure_records", ["session_uuid"])

    op.create_table(
        "glucose_records",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value_mmol", sa.Float, nullable=False),
        sa.Column("context", glucose_context, nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_glucose_user_time", "glucose_records", ["user_id", "measured_at"])

    op.create_table(
        "medications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("dose", sa.String(64)),
        sa.Column("notes", sa.Text),
        sa.Column("schedule_type", med_schedule_type, nullable=False),
        sa.Column("schedule_data", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("starts_on", sa.Date, nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("ends_on", sa.Date),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_meds_user_active", "medications", ["user_id", "is_active"])

    op.create_table(
        "medication_intakes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("medication_id", sa.Integer, sa.ForeignKey("medications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("taken_at", sa.DateTime(timezone=True)),
        sa.Column("taken", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("medication_id", "scheduled_at", name="uq_intake_med_scheduled"),
    )
    op.create_index("ix_intake_user_time", "medication_intakes", ["user_id", "taken_at"])

    op.create_table(
        "symptom_records",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("wellbeing", wellbeing_grade, nullable=False),
        sa.Column("symptoms", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("intensity", sa.Integer),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_symptom_user_time", "symptom_records", ["user_id", "occurred_at"])

    op.create_table(
        "meal_records",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("eaten_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meal_type", meal_type, nullable=False),
        sa.Column("tags", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_meal_user_time", "meal_records", ["user_id", "eaten_at"])

    op.create_table(
        "lab_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("drawn_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_chol", sa.Float),
        sa.Column("ldl", sa.Float),
        sa.Column("hdl", sa.Float),
        sa.Column("triglycerides", sa.Float),
        sa.Column("glucose_fasting", sa.Float),
        sa.Column("insulin_fasting", sa.Float),
        sa.Column("creatinine_umol", sa.Float),
        sa.Column("extra", postgresql.JSONB),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_lab_user_time", "lab_results", ["user_id", "drawn_at"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", alert_kind, nullable=False),
        sa.Column("severity", alert_severity, nullable=False),
        sa.Column("summary", sa.String(512), nullable=False),
        sa.Column("payload", postgresql.JSONB),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_by_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("dedup_key", sa.String(255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_alerts_user_kind_time", "alerts", ["user_id", "kind", "created_at"])

    op.create_table(
        "message_threads",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("doctor_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("doctor_id", "patient_id", name="uq_thread_doctor_patient"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("thread_id", sa.Integer, sa.ForeignKey("message_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_messages_thread_time", "messages", ["thread_id", "created_at"])

    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("medication_id", sa.Integer, sa.ForeignKey("medications.id", ondelete="CASCADE")),
        sa.Column("config", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_rem_user_kind", "reminders", ["user_id", "kind"])


def downgrade() -> None:
    for tbl in (
        "reminders", "messages", "message_threads", "alerts", "lab_results",
        "meal_records", "symptom_records", "medication_intakes", "medications",
        "glucose_records", "pressure_records", "users",
    ):
        op.drop_table(tbl)
    bind = op.get_bind()
    for e in (alert_severity, alert_kind, med_schedule_type, wellbeing_grade,
              meal_type, glucose_context, sex, user_role):
        e.drop(bind, checkfirst=True)
