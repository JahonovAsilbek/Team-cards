import os
import string
import random

from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import db
from states import CreateOrg, RenameOrg, AddParticipant, EditFIO, AddCardToParticipant
from keyboards import (
    user_menu, my_orgs_list, my_org_detail,
    participant_list, participant_detail,
    card_list_for_delete, done_button, format_card,
    join_request, org_members_list,
)

router = Router()
SUPER_ADMIN_ID = int(os.environ.get("SUPER_ADMIN", 0))


def generate_unique_id(length: int = 16) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


async def check_blocked(user_id: int) -> bool:
    return await db.is_blocked(user_id)


# ========================
# /start
# ========================

@router.message(CommandStart(deep_link=True))
async def cmd_start_with_link(message: Message, command: CommandObject, state: FSMContext):
    if await check_blocked(message.from_user.id):
        await message.answer("Siz bloklangansiz.")
        return
    await state.clear()
    await process_join(message, command.args)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    if await check_blocked(message.from_user.id):
        await message.answer("Siz bloklangansiz.")
        return
    await state.clear()
    await message.answer(
        "Assalomu alaykum! Quyidagi amallardan birini tanlang:",
        reply_markup=user_menu()
    )


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
    if await check_blocked(callback.from_user.id):
        await callback.answer("Siz bloklangansiz.", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "Quyidagi amallardan birini tanlang:",
        reply_markup=user_menu()
    )


# ========================
# Jamoa yaratish
# ========================

@router.callback_query(F.data == "create_org")
async def cb_create_org(callback: CallbackQuery, state: FSMContext):
    if await check_blocked(callback.from_user.id):
        await callback.answer("Siz bloklangansiz.", show_alert=True)
        return
    await state.set_state(CreateOrg.name)
    await callback.message.edit_text("Jamoa nomini kiriting:")


@router.message(CreateOrg.name)
async def process_create_org(message: Message, state: FSMContext):
    if await check_blocked(message.from_user.id):
        return
    name = message.text.strip()
    unique_id = generate_unique_id()
    user = message.from_user

    org_id = await db.create_org(name, unique_id, user.id)
    await db.add_user_to_org(user.id, org_id, user.full_name, user.username)

    await state.clear()
    bot_info = await message.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={unique_id}"
    await message.answer(
        f"Jamoa yaratildi!\n\n"
        f"Nomi: {name}\n\n"
        f"Ulanish havolasi:\n{link}\n\n"
        f"Shu havolani a'zolarga yuboring.",
        reply_markup=user_menu()
    )


# ========================
# Jamoalarim
# ========================

@router.callback_query(F.data == "my_orgs")
async def cb_my_orgs(callback: CallbackQuery, state: FSMContext):
    if await check_blocked(callback.from_user.id):
        await callback.answer("Siz bloklangansiz.", show_alert=True)
        return
    await state.clear()
    orgs = await db.get_user_orgs(callback.from_user.id)
    if not orgs:
        await callback.message.edit_text(
            "Sizda jamoalar yo'q.",
            reply_markup=user_menu()
        )
        return
    await callback.message.edit_text(
        "Jamoalaringiz:",
        reply_markup=my_orgs_list(orgs)
    )


# ========================
# Deep link orqali ulanish
# ========================

async def process_join(message: Message, unique_id: str):
    """Jamoaga ulanish logikasi (faqat link orqali)"""
    org = await db.get_org_by_unique_id(unique_id)
    if not org:
        await message.answer("Jamoa topilmadi.",
                             reply_markup=user_menu())
        return

    user = message.from_user
    org_id = org["id"]

    # Allaqachon a'zo bo'lsa
    if await db.is_org_member(user.id, org_id):
        await message.answer(f"Siz allaqachon «{org['name']}» jamoasiga ulangansiz!",
                             reply_markup=user_menu())
        return

    # Super admin to'g'ridan-to'g'ri ulanadi
    if user.id == SUPER_ADMIN_ID:
        await db.add_user_to_org(user.id, org_id, user.full_name, user.username)
        await message.answer(f"Siz «{org['name']}» jamoasiga ulandingiz!",
                             reply_markup=user_menu())
        return

    # Owner bo'lsa ham to'g'ridan-to'g'ri ulanadi
    if org["owner_id"] == user.id:
        await db.add_user_to_org(user.id, org_id, user.full_name, user.username)
        await message.answer(f"Siz «{org['name']}» jamoasiga ulandingiz!",
                             reply_markup=user_menu())
        return

    # Owner ga so'rov yuborish
    owner_id = org["owner_id"]
    user_name = user.full_name
    username = f" (@{user.username})" if user.username else ""

    await message.bot.send_message(
        owner_id,
        f"Yangi ulanish so'rovi!\n\n"
        f"Foydalanuvchi: {user_name}{username}\n"
        f"ID: `{user.id}`\n"
        f"Jamoa: {org['name']}",
        parse_mode="Markdown",
        reply_markup=join_request(user.id, org_id)
    )

    await message.answer(
        f"«{org['name']}» jamoasiga ulanish so'rovi yuborildi.\n"
        f"Jamoa egasi tasdiqlashini kuting.",
        reply_markup=user_menu()
    )


# ========================
# Jamoa ko'rish (org_view)
# ========================

@router.callback_query(F.data.startswith("org_view:"))
async def cb_org_view(callback: CallbackQuery, state: FSMContext):
    if await check_blocked(callback.from_user.id):
        await callback.answer("Siz bloklangansiz.", show_alert=True)
        return
    await state.clear()
    org_id = int(callback.data.split(":")[1])
    org = await db.get_org(org_id)
    if not org:
        await callback.answer("Jamoa topilmadi")
        return

    is_owner = await db.is_org_owner(callback.from_user.id, org_id)
    is_super = callback.from_user.id == SUPER_ADMIN_ID

    text = f"Jamoa: {org['name']}"

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=my_org_detail(org_id, is_owner or is_super)
    )


# ========================
# Owner: Nom o'zgartirish
# ========================

@router.callback_query(F.data.startswith("rename_org:"))
async def cb_rename_org(callback: CallbackQuery, state: FSMContext):
    if await check_blocked(callback.from_user.id):
        return
    org_id = int(callback.data.split(":")[1])
    is_owner = await db.is_org_owner(callback.from_user.id, org_id)
    if not is_owner and callback.from_user.id != SUPER_ADMIN_ID:
        await callback.answer("Sizda ruxsat yo'q")
        return
    await state.set_state(RenameOrg.name)
    await state.update_data(org_id=org_id)
    await callback.message.edit_text("Yangi nomni kiriting:")


@router.message(RenameOrg.name)
async def process_rename_org(message: Message, state: FSMContext):
    if await check_blocked(message.from_user.id):
        return
    data = await state.get_data()
    org_id = data["org_id"]
    new_name = message.text.strip()
    await db.rename_org(org_id, new_name)
    await state.clear()
    org = await db.get_org(org_id)
    is_owner = await db.is_org_owner(message.from_user.id, org_id)
    await message.answer(
        f"Jamoa nomi o'zgartirildi!\n\nJamoa: {org['name']}",
        reply_markup=my_org_detail(org_id, is_owner or message.from_user.id == SUPER_ADMIN_ID)
    )


# ========================
# Owner: Jamoani o'chirish
# ========================

@router.callback_query(F.data.startswith("delete_org:"))
async def cb_delete_org(callback: CallbackQuery):
    if await check_blocked(callback.from_user.id):
        return
    org_id = int(callback.data.split(":")[1])
    is_owner = await db.is_org_owner(callback.from_user.id, org_id)
    if not is_owner and callback.from_user.id != SUPER_ADMIN_ID:
        await callback.answer("Sizda ruxsat yo'q")
        return
    await db.delete_org(org_id)
    await callback.answer("Jamoa o'chirildi!")
    orgs = await db.get_user_orgs(callback.from_user.id)
    if not orgs:
        await callback.message.edit_text(
            "Sizda jamoalar yo'q.",
            reply_markup=user_menu()
        )
    else:
        await callback.message.edit_text(
            "Jamoalaringiz:",
            reply_markup=my_orgs_list(orgs)
        )


# ========================
# Jamoadan chiqish (a'zo)
# ========================

@router.callback_query(F.data.startswith("leave_org:"))
async def cb_leave_org(callback: CallbackQuery):
    if await check_blocked(callback.from_user.id):
        return
    org_id = int(callback.data.split(":")[1])
    if await db.is_org_owner(callback.from_user.id, org_id):
        await callback.answer("Siz egasiz, chiqib keta olmaysiz. Jamoani o'chiring.", show_alert=True)
        return
    await db.remove_user_from_org(callback.from_user.id, org_id)
    await callback.answer("Jamoadan chiqdingiz!")
    orgs = await db.get_user_orgs(callback.from_user.id)
    if not orgs:
        await callback.message.edit_text(
            "Sizda jamoalar yo'q.",
            reply_markup=user_menu()
        )
    else:
        await callback.message.edit_text(
            "Jamoalaringiz:",
            reply_markup=my_orgs_list(orgs)
        )


# ========================
# Owner: Havola ko'rsatish
# ========================

@router.callback_query(F.data.startswith("org_link:"))
async def cb_org_link(callback: CallbackQuery):
    if await check_blocked(callback.from_user.id):
        return
    org_id = int(callback.data.split(":")[1])
    org = await db.get_org(org_id)
    if not org:
        await callback.answer("Jamoa topilmadi")
        return
    bot_info = await callback.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={org['unique_id']}"
    await callback.answer()
    await callback.message.edit_text(
        f"Jamoa: {org['name']}\n\n"
        f"Ulanish havolasi:\n{link}",
        reply_markup=my_org_detail(org_id, True)
    )


# ========================
# Ishtirokchi qo'shish (faqat owner)
# ========================

@router.callback_query(F.data.startswith("add_participant:"))
async def cb_add_participant(callback: CallbackQuery, state: FSMContext):
    if await check_blocked(callback.from_user.id):
        return
    org_id = int(callback.data.split(":")[1])
    is_owner = await db.is_org_owner(callback.from_user.id, org_id)
    if not is_owner and callback.from_user.id != SUPER_ADMIN_ID:
        await callback.answer("Sizda ruxsat yo'q")
        return
    await state.set_state(AddParticipant.fio)
    await state.update_data(org_id=org_id, cards=[])
    await callback.message.edit_text("Ishtirokchi FIO ni kiriting:")


@router.message(AddParticipant.fio)
async def process_participant_fio(message: Message, state: FSMContext):
    if await check_blocked(message.from_user.id):
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
    if await check_blocked(message.from_user.id):
        return
    card = message.text.strip().replace(" ", "")
    if not card.isdigit() or len(card) != 16:
        await message.answer("Xato! Karta raqami 16 xonali bo'lishi kerak. Qayta kiriting:")
        return
    data = await state.get_data()
    cards = data.get("cards", [])
    if card in cards:
        await message.answer("Bu karta allaqachon qo'shilgan. Boshqa karta kiriting:")
        return
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
    if await check_blocked(callback.from_user.id):
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
    is_owner = await db.is_org_owner(callback.from_user.id, org_id)
    await callback.message.edit_text(
        f"Ishtirokchi qo'shildi!\n\nFIO: {fio}\nKartalar: {len(cards)} ta",
        reply_markup=my_org_detail(org_id, is_owner or callback.from_user.id == SUPER_ADMIN_ID)
    )


# ========================
# Ishtirokchilar ro'yxati
# ========================

@router.callback_query(F.data.startswith("list_participants:"))
async def cb_list_participants(callback: CallbackQuery):
    if await check_blocked(callback.from_user.id):
        return
    org_id = int(callback.data.split(":")[1])
    participants = await db.get_participants(org_id)
    if not participants:
        is_owner = await db.is_org_owner(callback.from_user.id, org_id)
        await callback.message.edit_text(
            "Ishtirokchilar yo'q.",
            reply_markup=my_org_detail(org_id, is_owner or callback.from_user.id == SUPER_ADMIN_ID)
        )
        return
    await callback.message.edit_text(
        "Ishtirokchilar:",
        reply_markup=participant_list(participants, org_id)
    )


# ========================
# Ishtirokchi tafsilotlari
# ========================

@router.callback_query(F.data.startswith("participant:"))
async def cb_participant_detail(callback: CallbackQuery, state: FSMContext):
    if await check_blocked(callback.from_user.id):
        return
    await state.clear()
    participant_id = int(callback.data.split(":")[1])
    p = await db.get_participant(participant_id)
    if not p:
        await callback.answer("Ishtirokchi topilmadi")
        return
    cards = await db.get_cards(participant_id)
    cards_text = "\n".join(f"`{format_card(c['card_number'])}`" for c in cards) if cards else "Kartalar yo'q"
    is_owner = await db.is_org_owner(callback.from_user.id, p["org_id"])
    await callback.message.edit_text(
        f"FIO: {p['fio']}\n\nKartalar:\n{cards_text}",
        parse_mode="Markdown",
        reply_markup=participant_detail(participant_id, p["org_id"],
                                       is_owner or callback.from_user.id == SUPER_ADMIN_ID)
    )


# ========================
# Owner: FIO o'zgartirish
# ========================

@router.callback_query(F.data.startswith("edit_fio:"))
async def cb_edit_fio(callback: CallbackQuery, state: FSMContext):
    if await check_blocked(callback.from_user.id):
        return
    participant_id = int(callback.data.split(":")[1])
    p = await db.get_participant(participant_id)
    if not p:
        await callback.answer("Ishtirokchi topilmadi")
        return
    is_owner = await db.is_org_owner(callback.from_user.id, p["org_id"])
    if not is_owner and callback.from_user.id != SUPER_ADMIN_ID:
        await callback.answer("Sizda ruxsat yo'q")
        return
    await state.set_state(EditFIO.fio)
    await state.update_data(participant_id=participant_id)
    await callback.message.edit_text("Yangi FIO ni kiriting:")


@router.message(EditFIO.fio)
async def process_edit_fio(message: Message, state: FSMContext):
    if await check_blocked(message.from_user.id):
        return
    data = await state.get_data()
    participant_id = data["participant_id"]
    new_fio = message.text.strip()
    await db.rename_participant(participant_id, new_fio)
    await state.clear()

    p = await db.get_participant(participant_id)
    cards = await db.get_cards(participant_id)
    cards_text = "\n".join(f"`{format_card(c['card_number'])}`" for c in cards) if cards else "Kartalar yo'q"
    is_owner = await db.is_org_owner(message.from_user.id, p["org_id"])
    await message.answer(
        f"FIO o'zgartirildi!\n\nFIO: {p['fio']}\n\nKartalar:\n{cards_text}",
        parse_mode="Markdown",
        reply_markup=participant_detail(participant_id, p["org_id"],
                                       is_owner or message.from_user.id == SUPER_ADMIN_ID)
    )


# ========================
# Karta qo'shish (faqat owner)
# ========================

@router.callback_query(F.data.startswith("add_card:"))
async def cb_add_card(callback: CallbackQuery, state: FSMContext):
    if await check_blocked(callback.from_user.id):
        return
    participant_id = int(callback.data.split(":")[1])
    p = await db.get_participant(participant_id)
    if not p:
        await callback.answer("Ishtirokchi topilmadi")
        return
    is_owner = await db.is_org_owner(callback.from_user.id, p["org_id"])
    if not is_owner and callback.from_user.id != SUPER_ADMIN_ID:
        await callback.answer("Sizda ruxsat yo'q")
        return
    await state.set_state(AddCardToParticipant.cards)
    await state.update_data(participant_id=participant_id, cards=[])
    await callback.message.edit_text(
        "Karta raqamini kiriting (16 xonali).\nTayyor bo'lganda tugmani bosing.",
        reply_markup=done_button()
    )


@router.message(AddCardToParticipant.cards)
async def process_add_card(message: Message, state: FSMContext):
    if await check_blocked(message.from_user.id):
        return
    card = message.text.strip().replace(" ", "")
    if not card.isdigit() or len(card) != 16:
        await message.answer("Xato! Karta raqami 16 xonali bo'lishi kerak. Qayta kiriting:")
        return
    data = await state.get_data()
    participant_id = data["participant_id"]
    # Duplikat tekshiruvi — shu sessiyada
    cards = data.get("cards", [])
    if card in cards:
        await message.answer("Bu karta allaqachon qo'shilgan. Boshqa karta kiriting:")
        return
    # Duplikat tekshiruvi — bazada
    if await db.card_exists(participant_id, card):
        await message.answer("Bu karta ishtirokchida allaqachon mavjud. Boshqa karta kiriting:")
        return
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
    if await check_blocked(callback.from_user.id):
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
    is_owner = await db.is_org_owner(callback.from_user.id, p["org_id"])
    await callback.message.edit_text(
        f"Kartalar qo'shildi!\n\nFIO: {p['fio']}\n\nKartalar:\n{cards_text}",
        parse_mode="Markdown",
        reply_markup=participant_detail(participant_id, p["org_id"],
                                       is_owner or callback.from_user.id == SUPER_ADMIN_ID)
    )


# ========================
# Owner: Karta o'chirish
# ========================

@router.callback_query(F.data.startswith("del_card:"))
async def cb_del_card_list(callback: CallbackQuery):
    if await check_blocked(callback.from_user.id):
        return
    participant_id = int(callback.data.split(":")[1])
    p = await db.get_participant(participant_id)
    if not p:
        await callback.answer("Ishtirokchi topilmadi")
        return
    is_owner = await db.is_org_owner(callback.from_user.id, p["org_id"])
    if not is_owner and callback.from_user.id != SUPER_ADMIN_ID:
        await callback.answer("Sizda ruxsat yo'q")
        return
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
    if await check_blocked(callback.from_user.id):
        return
    parts = callback.data.split(":")
    card_id = int(parts[1])
    participant_id = int(parts[2])
    p = await db.get_participant(participant_id)
    if not p:
        await callback.answer("Ishtirokchi topilmadi")
        return
    is_owner = await db.is_org_owner(callback.from_user.id, p["org_id"])
    if not is_owner and callback.from_user.id != SUPER_ADMIN_ID:
        await callback.answer("Sizda ruxsat yo'q")
        return
    await db.delete_card(card_id)
    await callback.answer("Karta o'chirildi!")

    cards = await db.get_cards(participant_id)
    cards_text = "\n".join(f"`{format_card(c['card_number'])}`" for c in cards) if cards else "Kartalar yo'q"
    await callback.message.edit_text(
        f"FIO: {p['fio']}\n\nKartalar:\n{cards_text}",
        parse_mode="Markdown",
        reply_markup=participant_detail(participant_id, p["org_id"],
                                       is_owner or callback.from_user.id == SUPER_ADMIN_ID)
    )


# ========================
# Owner: Ishtirokchini o'chirish
# ========================

@router.callback_query(F.data.startswith("del_participant:"))
async def cb_del_participant(callback: CallbackQuery):
    if await check_blocked(callback.from_user.id):
        return
    participant_id = int(callback.data.split(":")[1])
    p = await db.get_participant(participant_id)
    if not p:
        await callback.answer("Ishtirokchi topilmadi")
        return
    org_id = p["org_id"]
    is_owner = await db.is_org_owner(callback.from_user.id, org_id)
    if not is_owner and callback.from_user.id != SUPER_ADMIN_ID:
        await callback.answer("Sizda ruxsat yo'q")
        return
    await db.delete_participant(participant_id)
    await callback.answer("Ishtirokchi o'chirildi!")

    participants = await db.get_participants(org_id)
    if not participants:
        await callback.message.edit_text(
            "Ishtirokchilar yo'q.",
            reply_markup=my_org_detail(org_id, True)
        )
    else:
        await callback.message.edit_text(
            "Ishtirokchilar:",
            reply_markup=participant_list(participants, org_id)
        )


# ========================
# Owner: A'zolar ro'yxati
# ========================

@router.callback_query(F.data.startswith("list_members:"))
async def cb_list_members(callback: CallbackQuery):
    if await check_blocked(callback.from_user.id):
        return
    org_id = int(callback.data.split(":")[1])
    is_owner = await db.is_org_owner(callback.from_user.id, org_id)
    if not is_owner and callback.from_user.id != SUPER_ADMIN_ID:
        await callback.answer("Sizda ruxsat yo'q")
        return
    members = await db.get_org_members(org_id)
    if not members:
        await callback.message.edit_text(
            "A'zolar yo'q.",
            reply_markup=my_org_detail(org_id, True)
        )
        return
    await callback.message.edit_text(
        f"A'zolar ({len(members)} ta):\nO'chirish uchun ❌ tugmasini bosing.",
        reply_markup=org_members_list(members, org_id)
    )


@router.callback_query(F.data.startswith("remove_member:"))
async def cb_remove_member(callback: CallbackQuery):
    if await check_blocked(callback.from_user.id):
        return
    parts = callback.data.split(":")
    telegram_id = int(parts[1])
    org_id = int(parts[2])
    is_owner = await db.is_org_owner(callback.from_user.id, org_id)
    if not is_owner and callback.from_user.id != SUPER_ADMIN_ID:
        await callback.answer("Sizda ruxsat yo'q")
        return
    if await db.is_org_owner(telegram_id, org_id):
        await callback.answer("Jamoa egasini o'chirib bo'lmaydi!", show_alert=True)
        return
    await db.remove_user_from_org(telegram_id, org_id)
    await callback.answer("A'zo o'chirildi!")

    members = await db.get_org_members(org_id)
    if not members:
        await callback.message.edit_text(
            "A'zolar yo'q.",
            reply_markup=my_org_detail(org_id, True)
        )
    else:
        await callback.message.edit_text(
            f"A'zolar ({len(members)} ta):\nO'chirish uchun ❌ tugmasini bosing.",
            reply_markup=org_members_list(members, org_id)
        )


# ========================
# Ulanish so'rovlari (approve/deny)
# ========================

@router.callback_query(F.data.startswith("approve:"))
async def cb_approve_join(callback: CallbackQuery):
    parts = callback.data.split(":")
    telegram_id = int(parts[1])
    org_id = int(parts[2])

    org = await db.get_org(org_id)
    if not org:
        await callback.message.edit_text("Jamoa topilmadi.")
        return

    is_owner = await db.is_org_owner(callback.from_user.id, org_id)
    if not is_owner and callback.from_user.id != SUPER_ADMIN_ID:
        await callback.answer("Sizda ruxsat yo'q")
        return

    try:
        chat = await callback.bot.get_chat(telegram_id)
        full_name = chat.full_name
        username = chat.username
    except Exception:
        full_name = None
        username = None

    await db.add_user_to_org(telegram_id, org_id, full_name, username)

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ Tasdiqlandi!",
        parse_mode="Markdown",
        reply_markup=my_org_detail(org_id, True)
    )

    await callback.bot.send_message(
        telegram_id,
        f"Sizning so'rovingiz tasdiqlandi!\n"
        f"Siz «{org['name']}» jamoasiga ulandingiz.",
        reply_markup=user_menu()
    )


@router.callback_query(F.data.startswith("deny:"))
async def cb_deny_join(callback: CallbackQuery):
    parts = callback.data.split(":")
    telegram_id = int(parts[1])
    org_id = int(parts[2])

    org = await db.get_org(org_id)
    is_owner = org and await db.is_org_owner(callback.from_user.id, org_id)
    if not is_owner and callback.from_user.id != SUPER_ADMIN_ID:
        await callback.answer("Sizda ruxsat yo'q")
        return

    org_name = org["name"] if org else "Noma'lum"

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ Rad etildi!",
        parse_mode="Markdown",
        reply_markup=my_org_detail(org_id, True) if org else None
    )

    await callback.bot.send_message(
        telegram_id,
        f"Sizning «{org_name}» jamoasiga ulanish so'rovingiz rad etildi.",
        reply_markup=user_menu()
    )


# ========================
# Noop
# ========================

@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()
