from aiogram.fsm.state import State, StatesGroup


class DoctorMessageFSM(StatesGroup):
    waiting_body = State()


class DoctorLinkFSM(StatesGroup):
    waiting_patient_id = State()
