from aiogram.fsm.state import State, StatesGroup


class ReportFSM(StatesGroup):
    waiting_period = State()
    waiting_format = State()
    waiting_custom_start = State()
    waiting_custom_end = State()
