"""Real medical calculators (no stubs).

References:
* SCORE2 — ESC 2021 (Eur Heart J 42:2439–2454).  Implements the published
  age- and risk-region-specific β-coefficients and uncalibrated linear
  predictor with sex-specific baseline survival, then applies the regional
  recalibration scaling factors. Result is 10-year fatal+non-fatal CVD risk
  for adults aged 40-69 in apparently healthy population.
* BMI — kg/m².
* GFR — CKD-EPI 2021 race-free creatinine equation (NEJM 385:1737-1749).
* HOMA-IR — (fasting insulin µU/mL × fasting glucose mg/dL) / 405,
  equivalent to (insulin × glucose_mmol) / 22.5.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Literal

Sex = Literal["male", "female"]
ScoreRegion = Literal["low", "moderate", "high", "very_high"]


# ---------------------------------------------------------------- BMI
@dataclass(frozen=True)
class BMIResult:
    bmi: float
    category: str


def bmi(height_cm: float, weight_kg: float) -> BMIResult:
    if height_cm <= 0 or weight_kg <= 0:
        raise ValueError("height and weight must be positive")
    h = height_cm / 100.0
    value = weight_kg / (h * h)
    if value < 18.5:
        cat = "Дефицит массы"
    elif value < 25:
        cat = "Норма"
    elif value < 30:
        cat = "Избыточная масса"
    elif value < 35:
        cat = "Ожирение I ст."
    elif value < 40:
        cat = "Ожирение II ст."
    else:
        cat = "Ожирение III ст."
    return BMIResult(round(value, 1), cat)


# ---------------------------------------------------------------- GFR (CKD-EPI 2021)
@dataclass(frozen=True)
class GFRResult:
    egfr: float
    stage: str


def egfr_ckdepi_2021(creatinine_umol_l: float, age_years: int, sex: Sex) -> GFRResult:
    """eGFR by CKD-EPI 2021 (race-free) from serum creatinine in µmol/L."""
    if creatinine_umol_l <= 0 or age_years <= 0:
        raise ValueError("inputs must be positive")
    cr_mgdl = creatinine_umol_l / 88.4
    if sex == "female":
        kappa, alpha, sex_factor = 0.7, -0.241, 1.012
    else:
        kappa, alpha, sex_factor = 0.9, -0.302, 1.0
    ratio = cr_mgdl / kappa
    egfr = (
        142
        * (min(ratio, 1) ** alpha)
        * (max(ratio, 1) ** -1.200)
        * (0.9938 ** age_years)
        * sex_factor
    )
    if egfr >= 90:
        stage = "G1 (норма)"
    elif egfr >= 60:
        stage = "G2 (лёгкое снижение)"
    elif egfr >= 45:
        stage = "G3a"
    elif egfr >= 30:
        stage = "G3b"
    elif egfr >= 15:
        stage = "G4"
    else:
        stage = "G5"
    return GFRResult(round(egfr, 1), stage)


# ---------------------------------------------------------------- HOMA-IR
@dataclass(frozen=True)
class HomaIRResult:
    value: float
    interpretation: str


def homa_ir(glucose_mmol_l: float, insulin_uU_ml: float) -> HomaIRResult:
    if glucose_mmol_l <= 0 or insulin_uU_ml <= 0:
        raise ValueError("inputs must be positive")
    value = (glucose_mmol_l * insulin_uU_ml) / 22.5
    if value < 2.0:
        interp = "Норма"
    elif value < 2.7:
        interp = "Пограничный уровень"
    else:
        interp = "Признаки инсулинорезистентности"
    return HomaIRResult(round(value, 2), interp)


# ---------------------------------------------------------------- SCORE2
# ESC 2021 SCORE2 published coefficients (40–69 y, fatal+non-fatal CVD, 10y).
# Variables are centered as in the supplement.

_SCORE2_BETAS = {
    # sex -> { variable -> beta }
    "male": {
        "age": 0.3742, "smoker": 0.6012, "sbp": 0.2777,
        "tchol": 0.1458, "hdl": -0.2698,
        "smoker_age": -0.0755, "sbp_age": -0.0255,
        "tchol_age": -0.0281, "hdl_age": 0.0426,
    },
    "female": {
        "age": 0.4648, "smoker": 0.7744, "sbp": 0.3131,
        "tchol": 0.1002, "hdl": -0.2606,
        "smoker_age": -0.1088, "sbp_age": -0.0277,
        "tchol_age": -0.0226, "hdl_age": 0.0613,
    },
}

# Baseline 10-year risk of fatal+non-fatal CVD on the uncalibrated scale.
_SCORE2_BASELINE_S0 = {"male": 0.9605, "female": 0.9776}

# Regional scaling factors (ESC 2021, supplement Table S5)
_SCORE2_SCALE = {
    "low":       {"male": (-0.5699, 0.7476), "female": (-0.7380, 0.7019)},
    "moderate":  {"male": (-0.1565, 0.8009), "female": (-0.3143, 0.7701)},
    "high":      {"male": ( 0.3207, 0.9360), "female": ( 0.5710, 0.9369)},
    "very_high": {"male": ( 0.5836, 0.8294), "female": ( 0.9412, 0.8329)},
}


@dataclass(frozen=True)
class SCORE2Result:
    risk_pct: float
    category: str
    region: ScoreRegion


def score2(
    *,
    sex: Sex,
    age: int,
    smoker: bool,
    sbp_mmhg: float,
    total_chol_mmol: float,
    hdl_mmol: float,
    region: ScoreRegion = "high",
) -> SCORE2Result:
    """SCORE2 10-year fatal+non-fatal CVD risk (ages 40-69)."""
    if not 40 <= age <= 69:
        raise ValueError("SCORE2 is defined for ages 40–69")
    b = _SCORE2_BETAS[sex]
    cage = (age - 60) / 5.0
    csbp = (sbp_mmhg - 120) / 20.0
    ctc = total_chol_mmol - 6.0
    chdl = (hdl_mmol - 1.3) / 0.5
    smk = 1 if smoker else 0

    lp = (
        b["age"] * cage
        + b["smoker"] * smk
        + b["sbp"] * csbp
        + b["tchol"] * ctc
        + b["hdl"] * chdl
        + b["smoker_age"] * smk * cage
        + b["sbp_age"] * csbp * cage
        + b["tchol_age"] * ctc * cage
        + b["hdl_age"] * chdl * cage
    )
    s0 = _SCORE2_BASELINE_S0[sex]
    raw_risk = 1.0 - s0 ** math.exp(lp)

    a, k = _SCORE2_SCALE[region][sex]
    # Recalibration: 1 - exp(-exp(a + k * ln(-ln(1 - raw))))
    ln_neg_ln = math.log(-math.log(1 - raw_risk))
    recal = 1.0 - math.exp(-math.exp(a + k * ln_neg_ln))

    pct = round(recal * 100, 1)

    # ESC risk thresholds for ages <50 / 50-69 differ; common simplified:
    if age < 50:
        if pct < 2.5:
            cat = "Низкий"
        elif pct < 7.5:
            cat = "Умеренный"
        else:
            cat = "Высокий"
    else:
        if pct < 5:
            cat = "Низкий"
        elif pct < 10:
            cat = "Умеренный"
        else:
            cat = "Высокий"
    return SCORE2Result(pct, cat, region)


# ---------------------------------------------------------------- helpers
def age_from_birth(birth: date, today: date) -> int:
    years = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    return max(years, 0)
