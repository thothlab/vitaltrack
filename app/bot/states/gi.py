from aiogram.fsm.state import State, StatesGroup


class GIFSM(StatesGroup):
    waiting_time = State()
    waiting_pain = State()
    waiting_nausea = State()
    waiting_heartburn = State()
    waiting_bloating = State()
    waiting_stool = State()
    waiting_notes = State()
