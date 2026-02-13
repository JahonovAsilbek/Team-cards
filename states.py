from aiogram.fsm.state import State, StatesGroup


class AddOrg(StatesGroup):
    name = State()


class RenameOrg(StatesGroup):
    name = State()


class AddParticipant(StatesGroup):
    fio = State()
    cards = State()


class EditFIO(StatesGroup):
    fio = State()


class AddCardToParticipant(StatesGroup):
    cards = State()


class JoinOrg(StatesGroup):
    unique_id = State()


class UserAddCard(StatesGroup):
    fio = State()
    cards = State()
