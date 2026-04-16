from aiogram.fsm.state import State, StatesGroup


class NutritionFSM(StatesGroup):
    waiting_time = State()
    waiting_meal_type = State()
    waiting_tags = State()
    waiting_note = State()
