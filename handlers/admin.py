import os
import string
import random

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import db
from states import AddOrg, RenameOrg, AddParticipant, EditFIO, AddCardToParticipant
from keyboards import (
    admin_menu, org_list, org_detail,
    participant_list, participant_detail,
    card_list_for_delete, done_button, format_card,
    user_list,
)

router = Router()
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def generate_unique_id(length: int = 16) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


# --- /admin ---

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Admin panel:", reply_markup=admin_menu())


@router.callback_query(F.data == "admin_back")
async def cb_admin_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    await callback.message.edit_text("Admin panel:", reply_markup=admin_menu())


# --- Tashkilot qo'shish ---

@router.callback_query(F.data == "add_org")
async def cb_add_org(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AddOrg.name)
    await callback.message.edit_text("Tashkilot nomini kiriting:")


@router.message(AddOrg.name)
async def process_org_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    name = message.text.strip()
    unique_id = generate_unique_id()
    org_id = await db.create_org(name, unique_id)
    await state.clear()
    await message.answer(
        f"Tashkilot yaratildi!\n\n"
        f"Nomi: {name}\n"
        f"ID: `{unique_id}`",
        parse_mode="Markdown",
        reply_markup=admin_menu()
    )


# --- Tashkilotlar ro'yxati ---

@router.callback_query(F.data == "list_orgs")
async def cb_list_orgs(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    orgs = await db.get_all_orgs()
    if not orgs:
        await callback.message.edit_text(
            "Tashkilotlar yo'q.", reply_markup=admin_menu()
        )
        return
    await callback.message.edit_text(
        "Tashkilotlar:", reply_markup=org_list(orgs)
    )


# --- Tashkilot tafsilotlari ---

@router.callback_query(F.data.startswith("org:"))
async def cb_org_detail(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    org_id = int(callback.data.split(":")[1])
    org = await db.get_org(org_id)
    if not org:
        await callback.answer("Tashkilot topilmadi")
        return
    await callback.message.edit_text(
        f"Tashkilot: {org['name']}\n"
        f"Unique ID: `{org['unique_id']}`",
        parse_mode="Markdown",
        reply_markup=org_detail(org_id)
    )


# --- Tashkilot nomini o'zgartirish ---

@router.callback_query(F.data.startswith("rename_org:"))
async def cb_rename_org(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    org_id = int(callback.data.split(":")[1])
    await state.set_state(RenameOrg.name)
    await state.update_data(org_id=org_id)
    await callback.message.edit_text("Yangi nomni kiriting:")


@router.message(RenameOrg.name)
async def process_rename_org(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    org_id = data["org_id"]
    new_name = message.text.strip()
    await db.rename_org(org_id, new_name)
    await state.clear()
    org = await db.get_org(org_id)
    await message.answer(
        f"Tashkilot nomi o'zgartirildi!\n\n"
        f"Tashkilot: {org['name']}\n"
        f"Unique ID: `{org['unique_id']}`",
        parse_mode="Markdown",
        reply_markup=org_detail(org_id)
    )


# --- Tashkilotni o'chirish ---

@router.callback_query(F.data.startswith("delete_org:"))
async def cb_delete_org(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    org_id = int(callback.data.split(":")[1])
    await db.delete_org(org_id)
    await callback.answer("Tashkilot o'chirildi!")
    orgs = await db.get_all_orgs()
    if not orgs:
        await callback.message.edit_text(
            "Tashkilotlar yo'q.", reply_markup=admin_menu()
        )
    else:
        await callback.message.edit_text(
            "Tashkilotlar:", reply_markup=org_list(orgs)
        )


# --- Ishtirokchi qo'shish ---

@router.callback_query(F.data.startswith("add_participant:"))
async def cb_add_participant(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    org_id = int(callback.data.split(":")[1])
    await state.set_state(AddParticipant.fio)
    await state.update_data(org_id=org_id, cards=[])
    await callback.message.edit_text("Ishtirokchi FIO ni kiriting:")


@router.message(AddParticipant.fio)
async def process_participant_fio(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    fio = message.text.strip()
    await state.update_data(fio=fio)
    await state.set_state(AddParticipant.cards)
    await message.answer(
        "Karta raqamini kiriting (16 xonali).\n"
        "Bir nechta karta qo'shishingiz mumkin.\n"
        "Tayyor bo'lganda tugmani bosing.",
        reply_markup=done_button()
    )


@router.message(AddParticipant.cards)
async def process_participant_card(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
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


@router.callback_query(F.data == "done", AddParticipant.cards)
async def cb_done_participant(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
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
    await callback.message.edit_text(
        f"Ishtirokchi qo'shildi!\n\nFIO: {fio}\nKartalar: {len(cards)} ta",
        reply_markup=org_detail(org_id)
    )


# --- Ishtirokchilar ro'yxati ---

@router.callback_query(F.data.startswith("list_participants:"))
async def cb_list_participants(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    org_id = int(callback.data.split(":")[1])
    participants = await db.get_participants(org_id)
    if not participants:
        await callback.message.edit_text(
            "Ishtirokchilar yo'q.",
            reply_markup=org_detail(org_id)
        )
        return
    await callback.message.edit_text(
        "Ishtirokchilar:",
        reply_markup=participant_list(participants, org_id)
    )


# --- Ishtirokchi tafsilotlari ---

@router.callback_query(F.data.startswith("participant:"))
async def cb_participant_detail(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    participant_id = int(callback.data.split(":")[1])
    p = await db.get_participant(participant_id)
    if not p:
        await callback.answer("Ishtirokchi topilmadi")
        return
    cards = await db.get_cards(participant_id)
    cards_text = "\n".join(f"`{format_card(c['card_number'])}`" for c in cards) if cards else "Kartalar yo'q"
    await callback.message.edit_text(
        f"FIO: {p['fio']}\n\nKartalar:\n{cards_text}",
        parse_mode="Markdown",
        reply_markup=participant_detail(participant_id, p["org_id"])
    )


# --- FIO o'zgartirish ---

@router.callback_query(F.data.startswith("edit_fio:"))
async def cb_edit_fio(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    participant_id = int(callback.data.split(":")[1])
    await state.set_state(EditFIO.fio)
    await state.update_data(participant_id=participant_id)
    await callback.message.edit_text("Yangi FIO ni kiriting:")


@router.message(EditFIO.fio)
async def process_edit_fio(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    participant_id = data["participant_id"]
    new_fio = message.text.strip()
    await db.rename_participant(participant_id, new_fio)
    await state.clear()

    p = await db.get_participant(participant_id)
    cards = await db.get_cards(participant_id)
    cards_text = "\n".join(f"`{format_card(c['card_number'])}`" for c in cards) if cards else "Kartalar yo'q"
    await message.answer(
        f"FIO o'zgartirildi!\n\nFIO: {p['fio']}\n\nKartalar:\n{cards_text}",
        parse_mode="Markdown",
        reply_markup=participant_detail(participant_id, p["org_id"])
    )


# --- Ishtirokchiga karta qo'shish ---

@router.callback_query(F.data.startswith("add_card:"))
async def cb_add_card(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    participant_id = int(callback.data.split(":")[1])
    await state.set_state(AddCardToParticipant.cards)
    await state.update_data(participant_id=participant_id, cards=[])
    await callback.message.edit_text(
        "Karta raqamini kiriting (16 xonali).\nTayyor bo'lganda tugmani bosing.",
        reply_markup=done_button()
    )


@router.message(AddCardToParticipant.cards)
async def process_add_card_to_participant(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
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


@router.callback_query(F.data == "done", AddCardToParticipant.cards)
async def cb_done_add_card(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    participant_id = data["participant_id"]
    cards = data.get("cards", [])

    if not cards:
        await callback.answer("Kamida bitta karta kiriting!")
        return

    for card in cards:
        await db.add_card(participant_id, card)

    await state.clear()
    p = await db.get_participant(participant_id)
    all_cards = await db.get_cards(participant_id)
    cards_text = "\n".join(f"`{format_card(c['card_number'])}`" for c in all_cards)
    await callback.message.edit_text(
        f"Kartalar qo'shildi!\n\nFIO: {p['fio']}\n\nKartalar:\n{cards_text}",
        parse_mode="Markdown",
        reply_markup=participant_detail(participant_id, p["org_id"])
    )


# --- Karta o'chirish ---

@router.callback_query(F.data.startswith("del_card:"))
async def cb_del_card_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    participant_id = int(callback.data.split(":")[1])
    cards = await db.get_cards(participant_id)
    if not cards:
        await callback.answer("Kartalar yo'q!")
        return
    await callback.message.edit_text(
        "O'chirish uchun kartani tanlang:",
        reply_markup=card_list_for_delete(cards, participant_id)
    )


@router.callback_query(F.data.startswith("remove_card:"))
async def cb_remove_card(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    card_id = int(parts[1])
    participant_id = int(parts[2])
    await db.delete_card(card_id)
    await callback.answer("Karta o'chirildi!")

    p = await db.get_participant(participant_id)
    cards = await db.get_cards(participant_id)
    cards_text = "\n".join(f"`{format_card(c['card_number'])}`" for c in cards) if cards else "Kartalar yo'q"
    await callback.message.edit_text(
        f"FIO: {p['fio']}\n\nKartalar:\n{cards_text}",
        parse_mode="Markdown",
        reply_markup=participant_detail(participant_id, p["org_id"])
    )


# --- Ishtirokchini o'chirish ---

@router.callback_query(F.data.startswith("del_participant:"))
async def cb_del_participant(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    participant_id = int(callback.data.split(":")[1])
    p = await db.get_participant(participant_id)
    if not p:
        await callback.answer("Ishtirokchi topilmadi")
        return
    org_id = p["org_id"]
    await db.delete_participant(participant_id)
    await callback.answer("Ishtirokchi o'chirildi!")

    participants = await db.get_participants(org_id)
    if not participants:
        await callback.message.edit_text(
            "Ishtirokchilar yo'q.",
            reply_markup=org_detail(org_id)
        )
    else:
        await callback.message.edit_text(
            "Ishtirokchilar:",
            reply_markup=participant_list(participants, org_id)
        )


# --- Ulanish so'rovlari (approve/deny) ---

@router.callback_query(F.data.startswith("approve:"))
async def cb_approve_join(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    telegram_id = int(parts[1])
    org_id = int(parts[2])

    org = await db.get_org(org_id)
    if not org:
        await callback.message.edit_text("Tashkilot topilmadi.")
        return

    try:
        chat = await callback.bot.get_chat(telegram_id)
        full_name = chat.full_name
        username = chat.username
    except Exception:
        full_name = None
        username = None

    await db.set_user_session(telegram_id, org_id, full_name, username)

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ Tasdiqlandi!",
        parse_mode="Markdown"
    )

    await callback.bot.send_message(
        telegram_id,
        f"Sizning so'rovingiz tasdiqlandi!\n"
        f"Siz «{org['name']}» ga ulandingiz."
    )


@router.callback_query(F.data.startswith("deny:"))
async def cb_deny_join(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    telegram_id = int(parts[1])
    org_id = int(parts[2])

    org = await db.get_org(org_id)
    org_name = org["name"] if org else "Noma'lum"

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ Rad etildi!",
        parse_mode="Markdown"
    )

    await callback.bot.send_message(
        telegram_id,
        f"Sizning «{org_name}» ga ulanish so'rovingiz rad etildi."
    )


# --- Foydalanuvchilar ro'yxati ---

@router.callback_query(F.data.startswith("list_users:"))
async def cb_list_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    org_id = int(callback.data.split(":")[1])
    users = await db.get_org_users(org_id)
    if not users:
        await callback.message.edit_text(
            "Foydalanuvchilar yo'q.",
            reply_markup=org_detail(org_id)
        )
        return

    await callback.message.edit_text(
        f"Foydalanuvchilar ({len(users)} ta):\n"
        f"O'chirish uchun ❌ tugmasini bosing.",
        reply_markup=user_list(users, org_id)
    )


@router.callback_query(F.data.startswith("remove_user:"))
async def cb_remove_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    telegram_id = int(parts[1])
    org_id = int(parts[2])
    await db.delete_user_session(telegram_id)
    await callback.answer("Foydalanuvchi o'chirildi!")

    users = await db.get_org_users(org_id)
    if not users:
        await callback.message.edit_text(
            "Foydalanuvchilar yo'q.",
            reply_markup=org_detail(org_id)
        )
    else:
        await callback.message.edit_text(
            f"Foydalanuvchilar ({len(users)} ta):\n"
            f"O'chirish uchun ❌ tugmasini bosing.",
            reply_markup=user_list(users, org_id)
        )


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()
