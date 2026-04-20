from aiogram.fsm.state import State, StatesGroup


class ProfileWizardFSM(StatesGroup):
    """Full sequential wizard. Each step accepts skip/cancel."""
    waiting_sex = State()
    waiting_birth = State()
    waiting_height = State()
    waiting_weight = State()
    waiting_smoker = State()
    waiting_diabetes = State()


class ProfileFieldFSM(StatesGroup):
    """Single-field edit from the profile summary."""
    waiting_birth = State()
    waiting_height = State()
    waiting_weight = State()
