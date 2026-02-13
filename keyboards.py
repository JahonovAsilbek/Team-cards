from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Tashkilot qo'shish", callback_data="add_org")],
        [InlineKeyboardButton(text="Tashkilotlar ro'yxati", callback_data="list_orgs")],
    ])


def org_list(orgs):
    buttons = [
        [InlineKeyboardButton(text=org["name"], callback_data=f"org:{org['id']}")]
        for org in orgs
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def org_detail(org_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Nomini o'zgartirish", callback_data=f"rename_org:{org_id}")],
        [InlineKeyboardButton(text="O'chirish", callback_data=f"delete_org:{org_id}")],
        [InlineKeyboardButton(text="Ishtirokchi qo'shish", callback_data=f"add_participant:{org_id}")],
        [InlineKeyboardButton(text="Ishtirokchilar ro'yxati", callback_data=f"list_participants:{org_id}")],
        [InlineKeyboardButton(text="Foydalanuvchilar", callback_data=f"list_users:{org_id}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="list_orgs")],
    ])


def participant_list(participants, org_id: int):
    buttons = [
        [InlineKeyboardButton(text=p["fio"], callback_data=f"participant:{p['id']}")]
        for p in participants
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"org:{org_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def participant_detail(participant_id: int, org_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="FIO o'zgartirish", callback_data=f"edit_fio:{participant_id}")],
        [InlineKeyboardButton(text="Karta qo'shish", callback_data=f"add_card:{participant_id}")],
        [InlineKeyboardButton(text="Karta o'chirish", callback_data=f"del_card:{participant_id}")],
        [InlineKeyboardButton(text="Ishtirokchini o'chirish", callback_data=f"del_participant:{participant_id}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"list_participants:{org_id}")],
    ])


def card_list_for_delete(cards, participant_id: int):
    buttons = [
        [InlineKeyboardButton(
            text=format_card(c["card_number"]),
            callback_data=f"remove_card:{c['id']}:{participant_id}"
        )]
        for c in cards
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"participant:{participant_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def done_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tayyor", callback_data="done")],
    ])


def user_list(users, org_id: int):
    buttons = []
    for u in users:
        name = u["full_name"] or str(u["telegram_id"])
        buttons.append([
            InlineKeyboardButton(text=name, callback_data=f"noop"),
            InlineKeyboardButton(text="❌", callback_data=f"remove_user:{u['telegram_id']}:{org_id}"),
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"org:{org_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def join_request(telegram_id: int, org_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ruxsat", callback_data=f"approve:{telegram_id}:{org_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"deny:{telegram_id}:{org_id}"),
        ],
    ])


def format_card(card_number: str) -> str:
    return f"{card_number[:4]} {card_number[4:8]} {card_number[8:12]} {card_number[12:]}"
