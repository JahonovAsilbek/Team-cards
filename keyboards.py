from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)


def format_card(card_number: str) -> str:
    return f"{card_number[:4]} {card_number[4:8]} {card_number[8:12]} {card_number[12:]}"


# --- Doimiy menyu (ReplyKeyboard) ---

BTN_CREATE = "➕ Jamoa yaratish"
BTN_MY_ORGS = "📋 Jamoalarim"


def user_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_CREATE), KeyboardButton(text=BTN_MY_ORGS)],
        ],
        resize_keyboard=True,
    )


def my_orgs_list(orgs):
    buttons = [
        [InlineKeyboardButton(text=f"📁 {org['name']}", callback_data=f"org_view:{org['id']}")]
        for org in orgs
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def my_org_detail(org_id: int, is_owner: bool):
    if is_owner:
        return owner_org_detail(org_id)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Ishtirokchilar", callback_data=f"list_participants:{org_id}"),
            InlineKeyboardButton(text="🚪 Chiqish", callback_data=f"leave_org:{org_id}"),
        ],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="my_orgs")],
    ])


def owner_org_detail(org_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Ishtirokchi", callback_data=f"add_participant:{org_id}"),
            InlineKeyboardButton(text="👥 Ishtirokchilar", callback_data=f"list_participants:{org_id}"),
        ],
        [
            InlineKeyboardButton(text="👤 A'zolar", callback_data=f"list_members:{org_id}"),
            InlineKeyboardButton(text="🔗 Havola", callback_data=f"org_link:{org_id}"),
        ],
        [
            InlineKeyboardButton(text="✏️ Nom", callback_data=f"rename_org:{org_id}"),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"delete_org:{org_id}"),
        ],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="my_orgs")],
    ])


def org_members_list(members, org_id: int):
    buttons = []
    for m in members:
        name = m["full_name"] or str(m["telegram_id"])
        buttons.append([
            InlineKeyboardButton(text=f"👤 {name}", callback_data="noop"),
            InlineKeyboardButton(text="❌", callback_data=f"remove_member:{m['telegram_id']}:{org_id}"),
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"org_view:{org_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# --- Ishtirokchilar ---

def participant_list(participants, org_id: int):
    buttons = [
        [InlineKeyboardButton(text=f"👤 {p['fio']}", callback_data=f"participant:{p['id']}")]
        for p in participants
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"org_view:{org_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def participant_detail(participant_id: int, org_id: int, is_owner: bool = True):
    if is_owner:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ FIO", callback_data=f"edit_fio:{participant_id}"),
                InlineKeyboardButton(text="💳 Qo'shish", callback_data=f"add_card:{participant_id}"),
            ],
            [
                InlineKeyboardButton(text="🗑 Karta", callback_data=f"del_card:{participant_id}"),
                InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_participant:{participant_id}"),
            ],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"list_participants:{org_id}")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"list_participants:{org_id}")],
    ])


def card_list_for_delete(cards, participant_id: int):
    buttons = [
        [InlineKeyboardButton(
            text=f"💳 {format_card(c['card_number'])}",
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


def join_request(telegram_id: int, org_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ruxsat", callback_data=f"approve:{telegram_id}:{org_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"deny:{telegram_id}:{org_id}"),
        ],
    ])


# --- Super admin ---

def super_admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Jamoalar", callback_data="sa_all_orgs"),
            InlineKeyboardButton(text="🚫 Bloklangan", callback_data="sa_blocked_users"),
        ],
        [InlineKeyboardButton(text="🔒 User bloklash", callback_data="sa_block_user")],
    ])


def sa_org_list(orgs):
    buttons = [
        [InlineKeyboardButton(text=f"📁 {org['name']}", callback_data=f"sa_org:{org['id']}")]
        for org in orgs
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="sa_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sa_org_detail(org_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Ishtirokchilar", callback_data=f"sa_participants:{org_id}"),
            InlineKeyboardButton(text="👤 A'zolar", callback_data=f"sa_members:{org_id}"),
        ],
        [InlineKeyboardButton(text="🗑 Jamoani o'chirish", callback_data=f"sa_delete_org:{org_id}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="sa_all_orgs")],
    ])


def blocked_users_list(users):
    buttons = [
        [InlineKeyboardButton(
            text=f"🚫 {u['telegram_id']}",
            callback_data=f"sa_unblock:{u['telegram_id']}"
        )]
        for u in users
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="sa_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
