from aiogram.fsm.state import State, StatesGroup


class SymptomFSM(StatesGroup):
    waiting_time = State()
    waiting_wellbeing = State()
    waiting_symptoms = State()
    waiting_intensity = State()
    waiting_note = State()
