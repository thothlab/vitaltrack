from aiogram.fsm.state import State, StatesGroup


class PressureFSM(StatesGroup):
    waiting_time = State()
    waiting_systolic = State()
    waiting_diastolic = State()
    waiting_pulse = State()
    waiting_more = State()
