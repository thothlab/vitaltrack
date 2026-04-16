from aiogram.fsm.state import State, StatesGroup


class BMIFSM(StatesGroup):
    waiting_height = State()
    waiting_weight = State()


class GFRFSM(StatesGroup):
    waiting_sex = State()
    waiting_age = State()
    waiting_cr = State()


class HOMAFSM(StatesGroup):
    waiting_glucose = State()
    waiting_insulin = State()


class SCOREFSM(StatesGroup):
    waiting_sex = State()
    waiting_age = State()
    waiting_smoker = State()
    waiting_sbp = State()
    waiting_tc = State()
    waiting_hdl = State()
    waiting_region = State()
