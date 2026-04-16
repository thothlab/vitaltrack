from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.bot.keyboards.common import cancel_kb
from app.bot.keyboards.patient import calc_menu
from app.bot.states.calculators import BMIFSM, GFRFSM, HOMAFSM, SCOREFSM
from app.services.calculators import (
    age_from_birth,
    bmi,
    egfr_ckdepi_2021,
    homa_ir,
    score2,
)
from app.utils.i18n import t

router = Router(name="calculators")


# ----- BMI -----
@router.callback_query(F.data == "calc:bmi")
async def bmi_start(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BMIFSM.waiting_height)
    await cq.message.edit_text("Рост, см:", reply_markup=cancel_kb())
    await cq.answer()


@router.message(BMIFSM.waiting_height)
async def bmi_h(message: Message, state: FSMContext) -> None:
    try:
        h = float((message.text or "").replace(",", "."))
    except ValueError:
        await message.answer("Нужно число.")
        return
    await state.update_data(h=h)
    await state.set_state(BMIFSM.waiting_weight)
    await message.answer("Вес, кг:", reply_markup=cancel_kb())


@router.message(BMIFSM.waiting_weight)
async def bmi_w(message: Message, state: FSMContext) -> None:
    try:
        w = float((message.text or "").replace(",", "."))
    except ValueError:
        await message.answer("Нужно число.")
        return
    data = await state.get_data()
    res = bmi(data["h"], w)
    await state.clear()
    await message.answer(f"BMI = {res.bmi} → {res.category}", reply_markup=calc_menu())


# ----- GFR -----
def _sex_kb(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Муж", callback_data=f"{prefix}:male"),
        InlineKeyboardButton(text="Жен", callback_data=f"{prefix}:female"),
    ]])


@router.callback_query(F.data == "calc:gfr")
async def gfr_start(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GFRFSM.waiting_sex)
    await cq.message.edit_text("Пол:", reply_markup=_sex_kb("gfr_sex"))
    await cq.answer()


@router.callback_query(GFRFSM.waiting_sex, F.data.startswith("gfr_sex:"))
async def gfr_sex(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(sex=cq.data.split(":")[1])
    await state.set_state(GFRFSM.waiting_age)
    await cq.message.edit_text("Возраст, лет:", reply_markup=cancel_kb())
    await cq.answer()


@router.message(GFRFSM.waiting_age)
async def gfr_age(message: Message, state: FSMContext) -> None:
    if not (message.text or "").strip().isdigit():
        await message.answer("Нужно целое число.")
        return
    await state.update_data(age=int(message.text))
    await state.set_state(GFRFSM.waiting_cr)
    await message.answer("Креатинин, µмоль/л:", reply_markup=cancel_kb())


@router.message(GFRFSM.waiting_cr)
async def gfr_cr(message: Message, state: FSMContext) -> None:
    try:
        cr = float((message.text or "").replace(",", "."))
    except ValueError:
        await message.answer("Нужно число.")
        return
    data = await state.get_data()
    res = egfr_ckdepi_2021(cr, int(data["age"]), data["sex"])
    await state.clear()
    await message.answer(
        f"eGFR (CKD-EPI 2021) = {res.egfr} мл/мин/1.73м² → {res.stage}",
        reply_markup=calc_menu(),
    )


# ----- HOMA-IR -----
@router.callback_query(F.data == "calc:homa")
async def homa_start(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(HOMAFSM.waiting_glucose)
    await cq.message.edit_text("Глюкоза натощак, ммоль/л:", reply_markup=cancel_kb())
    await cq.answer()


@router.message(HOMAFSM.waiting_glucose)
async def homa_glu(message: Message, state: FSMContext) -> None:
    try:
        g = float((message.text or "").replace(",", "."))
    except ValueError:
        await message.answer("Нужно число.")
        return
    await state.update_data(g=g)
    await state.set_state(HOMAFSM.waiting_insulin)
    await message.answer("Инсулин натощак, µU/mL:", reply_markup=cancel_kb())


@router.message(HOMAFSM.waiting_insulin)
async def homa_ins(message: Message, state: FSMContext) -> None:
    try:
        i = float((message.text or "").replace(",", "."))
    except ValueError:
        await message.answer("Нужно число.")
        return
    data = await state.get_data()
    res = homa_ir(data["g"], i)
    await state.clear()
    await message.answer(f"HOMA-IR = {res.value} → {res.interpretation}",
                         reply_markup=calc_menu())


# ----- SCORE2 -----
@router.callback_query(F.data == "calc:score")
async def score_start(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SCOREFSM.waiting_sex)
    await cq.message.edit_text("Пол:", reply_markup=_sex_kb("sc_sex"))
    await cq.answer()


@router.callback_query(SCOREFSM.waiting_sex, F.data.startswith("sc_sex:"))
async def score_sex(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(sex=cq.data.split(":")[1])
    await state.set_state(SCOREFSM.waiting_age)
    await cq.message.edit_text("Возраст 40–69, лет:", reply_markup=cancel_kb())
    await cq.answer()


@router.message(SCOREFSM.waiting_age)
async def score_age(message: Message, state: FSMContext) -> None:
    if not (message.text or "").strip().isdigit():
        await message.answer("Нужно целое число.")
        return
    age = int(message.text)
    if not 40 <= age <= 69:
        await message.answer("SCORE2 рассчитывается для возраста 40–69 лет.")
        return
    await state.update_data(age=age)
    await state.set_state(SCOREFSM.waiting_smoker)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("yes"), callback_data="sc_smk:yes"),
        InlineKeyboardButton(text=t("no"), callback_data="sc_smk:no"),
    ]])
    await message.answer("Курит?", reply_markup=kb)


@router.callback_query(SCOREFSM.waiting_smoker, F.data.startswith("sc_smk:"))
async def score_smoker(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(smoker=(cq.data.split(":")[1] == "yes"))
    await state.set_state(SCOREFSM.waiting_sbp)
    await cq.message.edit_text("САД, мм рт.ст.:", reply_markup=cancel_kb())
    await cq.answer()


@router.message(SCOREFSM.waiting_sbp)
async def score_sbp(message: Message, state: FSMContext) -> None:
    if not (message.text or "").strip().isdigit():
        await message.answer("Нужно число.")
        return
    await state.update_data(sbp=int(message.text))
    await state.set_state(SCOREFSM.waiting_tc)
    await message.answer("Общий холестерин, ммоль/л:", reply_markup=cancel_kb())


@router.message(SCOREFSM.waiting_tc)
async def score_tc(message: Message, state: FSMContext) -> None:
    try:
        tc = float((message.text or "").replace(",", "."))
    except ValueError:
        await message.answer("Нужно число.")
        return
    await state.update_data(tc=tc)
    await state.set_state(SCOREFSM.waiting_hdl)
    await message.answer("ЛПВП, ммоль/л:", reply_markup=cancel_kb())


@router.message(SCOREFSM.waiting_hdl)
async def score_hdl(message: Message, state: FSMContext) -> None:
    try:
        hdl = float((message.text or "").replace(",", "."))
    except ValueError:
        await message.answer("Нужно число.")
        return
    await state.update_data(hdl=hdl)
    await state.set_state(SCOREFSM.waiting_region)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Низкий риск", callback_data="sc_reg:low"),
        InlineKeyboardButton(text="Умеренный", callback_data="sc_reg:moderate"),
    ], [
        InlineKeyboardButton(text="Высокий", callback_data="sc_reg:high"),
        InlineKeyboardButton(text="Очень высокий", callback_data="sc_reg:very_high"),
    ]])
    await message.answer("Регион риска:", reply_markup=kb)


@router.callback_query(SCOREFSM.waiting_region, F.data.startswith("sc_reg:"))
async def score_region(cq: CallbackQuery, state: FSMContext) -> None:
    region = cq.data.split(":")[1]
    data = await state.get_data()
    res = score2(
        sex=data["sex"], age=int(data["age"]), smoker=bool(data["smoker"]),
        sbp_mmhg=float(data["sbp"]), total_chol_mmol=float(data["tc"]),
        hdl_mmol=float(data["hdl"]), region=region,
    )
    await state.clear()
    await cq.message.edit_text(
        f"SCORE2: 10-летний риск ССЗ = {res.risk_pct}% → {res.category}\n"
        f"(Регион: {res.region})",
        reply_markup=calc_menu(),
    )
    await cq.answer()
