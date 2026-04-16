from aiogram.fsm.state import State, StatesGroup


class LabFSM(StatesGroup):
    waiting_date = State()
    waiting_total_chol = State()
    waiting_ldl = State()
    waiting_hdl = State()
    waiting_tg = State()
    waiting_glucose = State()
    waiting_insulin = State()
    waiting_creatinine = State()
