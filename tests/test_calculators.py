import math

import pytest

from app.services.calculators import (
    bmi,
    egfr_ckdepi_2021,
    homa_ir,
    score2,
)


def test_bmi_basic():
    r = bmi(170, 70)
    assert r.bmi == pytest.approx(24.2, abs=0.1)
    assert r.category == "Норма"


def test_bmi_obese():
    r = bmi(170, 105)
    assert r.bmi >= 30
    assert "Ожирение" in r.category


def test_bmi_invalid():
    with pytest.raises(ValueError):
        bmi(0, 70)


def test_egfr_normal_male():
    # 50yo male, creatinine 90 µmol/L → ~84 mL/min/1.73m²
    r = egfr_ckdepi_2021(creatinine_umol_l=90, age_years=50, sex="male")
    assert 75 <= r.egfr <= 95
    assert r.stage.startswith(("G1", "G2"))


def test_egfr_low_female():
    r = egfr_ckdepi_2021(creatinine_umol_l=180, age_years=70, sex="female")
    assert r.egfr < 45


def test_homa_ir_normal():
    r = homa_ir(glucose_mmol_l=4.5, insulin_uU_ml=5)
    assert r.value < 2
    assert r.interpretation == "Норма"


def test_homa_ir_high():
    r = homa_ir(glucose_mmol_l=6.0, insulin_uU_ml=15)
    assert r.value > 2.7
    assert "инсулинорезистент" in r.interpretation.lower()


def test_score2_runs_in_range():
    r = score2(
        sex="male", age=55, smoker=True,
        sbp_mmhg=140, total_chol_mmol=5.5, hdl_mmol=1.0,
        region="high",
    )
    assert 0 < r.risk_pct < 100
    assert r.category in {"Низкий", "Умеренный", "Высокий"}


def test_score2_sex_dependence():
    f = score2(sex="female", age=55, smoker=False, sbp_mmhg=130,
               total_chol_mmol=5.0, hdl_mmol=1.4, region="moderate")
    m = score2(sex="male", age=55, smoker=False, sbp_mmhg=130,
               total_chol_mmol=5.0, hdl_mmol=1.4, region="moderate")
    # Men in same region/risk profile generally score higher
    assert m.risk_pct > f.risk_pct


def test_score2_age_bound():
    with pytest.raises(ValueError):
        score2(sex="male", age=70, smoker=False, sbp_mmhg=120,
               total_chol_mmol=5.0, hdl_mmol=1.4, region="high")
