from aiogram.fsm.state import State, StatesGroup


class CreateOrg(StatesGroup):
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


class BlockUser(StatesGroup):
    telegram_id = State()
