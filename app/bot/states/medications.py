from aiogram.fsm.state import State, StatesGroup


class MedCreateFSM(StatesGroup):
    waiting_name = State()
    waiting_dose = State()
    waiting_schedule_type = State()
    waiting_schedule_data = State()


class MedIntakeFSM(StatesGroup):
    waiting_medication = State()
    waiting_time = State()
