from aiogram.fsm.state import State, StatesGroup


class HeadacheFSM(StatesGroup):
    waiting_time = State()
    waiting_intensity = State()
    waiting_location = State()
    waiting_character = State()
    waiting_assoc = State()      # associated symptoms multi-select
    waiting_triggers = State()   # triggers multi-select
    waiting_disability = State()
    waiting_duration = State()
    waiting_notes = State()
