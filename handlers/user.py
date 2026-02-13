import os

from aiogram import Router, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import db
from states import UserAddCard, JoinOrg
from keyboards import done_button, format_card, join_request

router = Router()
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))


async def process_join(message: Message, unique_id: str):
    """Tashkilotga ulanish logikasi"""
    org = await db.get_org_by_unique_id(unique_id)
    if not org:
        await message.answer("Tashkilot topilmadi. Qayta tekshirib ko'ring.")
        return

    # Admin to'g'ridan-to'g'ri ulanadi
    if message.from_user.id == ADMIN_ID:
        await db.set_user_session(
            message.from_user.id, org["id"],
            message.from_user.full_name, message.from_user.username
        )
        await message.answer(f"Siz «{org['name']}» ga ulandingiz!")
        return

    # Allaqachon ulangan bo'lsa
    session = await db.get_user_session(message.from_user.id)
    if session and session["org_id"] == org["id"]:
        await message.answer(f"Siz allaqachon «{org['name']}» ga ulangansiz!")
        return

    # Adminga so'rov yuborish
    user = message.from_user
    user_name = user.full_name
    username = f" (@{user.username})" if user.username else ""

    await message.bot.send_message(
        ADMIN_ID,
        f"Yangi ulanish so'rovi!\n\n"
        f"Foydalanuvchi: {user_name}{username}\n"
        f"ID: `{user.id}`\n"
        f"Tashkilot: {org['name']}",
        parse_mode="Markdown",
        reply_markup=join_request(user.id, org["id"])
    )

    await message.answer(
        f"«{org['name']}» ga ulanish so'rovi yuborildi.\n"
        f"Admin tasdiqlashini kuting."
    )


@router.message(CommandStart(deep_link=True))
async def cmd_start_with_link(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    await process_join(message, command.args)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    session = await db.get_user_session(message.from_user.id)
    if session:
        org = await db.get_org(session["org_id"])
        if org:
            await message.answer(
                f"Siz «{org['name']}» tashkilotiga ulangansiz.\n\n"
                f"Karta qo'shish uchun /add_card buyrug'ini yuboring."
            )
            return

    await state.set_state(JoinOrg.unique_id)
    await message.answer(
        "Assalomu alaykum! Tashkilotga ulanish uchun "
        "tashkilot ID sini kiriting:"
    )


@router.message(JoinOrg.unique_id)
async def process_join_org(message: Message, state: FSMContext):
    unique_id = message.text.strip()
    if len(unique_id) != 16:
        await message.answer("Tashkilot ID si 16 belgidan iborat bo'lishi kerak. Qayta kiriting:")
        return
    await state.clear()
    await process_join(message, unique_id)


@router.message(Command("add_card"))
async def cmd_add_card(message: Message, state: FSMContext):
    session = await db.get_user_session(message.from_user.id)
    if not session:
        await message.answer("Avval tashkilotga ulaning. /start buyrug'ini yuboring.")
        return
    await state.set_state(UserAddCard.fio)
    await state.update_data(org_id=session["org_id"], cards=[])
    await message.answer("Ishtirokchi FIO ni kiriting:")


@router.message(UserAddCard.fio)
async def process_user_fio(message: Message, state: FSMContext):
    fio = message.text.strip()
    await state.update_data(fio=fio)
    await state.set_state(UserAddCard.cards)
    await message.answer(
        "Karta raqamini kiriting (16 xonali).\n"
        "Bir nechta karta qo'shishingiz mumkin.\n"
        "Tayyor bo'lganda tugmani bosing.",
        reply_markup=done_button()
    )


@router.message(UserAddCard.cards)
async def process_user_card(message: Message, state: FSMContext):
    card = message.text.strip().replace(" ", "")
    if not card.isdigit() or len(card) != 16:
        await message.answer("Xato! Karta raqami 16 xonali bo'lishi kerak. Qayta kiriting:")
        return
    data = await state.get_data()
    cards = data.get("cards", [])
    cards.append(card)
    await state.update_data(cards=cards)
    await message.answer(
        f"Karta qo'shildi: `{format_card(card)}`\n"
        f"Yana karta kiriting yoki Tayyor tugmasini bosing.",
        parse_mode="Markdown",
        reply_markup=done_button()
    )


@router.callback_query(F.data == "done", UserAddCard.cards)
async def cb_done_user_card(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    org_id = data["org_id"]
    fio = data["fio"]
    cards = data.get("cards", [])

    if not cards:
        await callback.answer("Kamida bitta karta kiriting!")
        return

    participant_id = await db.create_participant(org_id, fio)
    for card in cards:
        await db.add_card(participant_id, card)

    await state.clear()
    cards_text = "\n".join(f"`{format_card(c)}`" for c in cards)
    await callback.message.edit_text(
        f"Ishtirokchi qo'shildi!\n\nFIO: {fio}\n\nKartalar:\n{cards_text}",
        parse_mode="Markdown"
    )
