from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"


class Sex(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"


class GlucoseContext(str, enum.Enum):
    FASTING = "fasting"
    BEFORE_MEAL = "before_meal"
    POST_MEAL = "post_meal"
    BEDTIME = "bedtime"
    RANDOM = "random"


class MealType(str, enum.Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class WellbeingGrade(str, enum.Enum):
    GREAT = "great"
    GOOD = "good"
    OK = "ok"
    POOR = "poor"
    BAD = "bad"


class MedScheduleType(str, enum.Enum):
    FIXED_TIMES = "fixed_times"      # list of HH:MM in user TZ
    EVERY_N_HOURS = "every_n_hours"  # interval, optional anchor
    AS_NEEDED = "as_needed"          # PRN, no reminders


class AlertKind(str, enum.Enum):
    BP_HIGH = "bp_high"
    BP_LOW = "bp_low"
    GLUCOSE_HIGH = "glucose_high"
    GLUCOSE_LOW = "glucose_low"
    MED_MISSED = "med_missed"
    NO_DATA = "no_data"


class AlertSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ReportPeriod(str, enum.Enum):
    WEEK = "7d"
    MONTH = "30d"
    QUARTER = "90d"
    CUSTOM = "custom"


class ReportFormat(str, enum.Enum):
    TEXT = "text"
    PDF = "pdf"
    CSV = "csv"
