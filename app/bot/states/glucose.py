from aiogram.fsm.state import State, StatesGroup


class GlucoseFSM(StatesGroup):
    waiting_time = State()
    waiting_value = State()
    waiting_context = State()
