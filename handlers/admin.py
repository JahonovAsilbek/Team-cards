import os

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import db
from states import BlockUser
from keyboards import (
    super_admin_menu, sa_org_list, sa_org_detail,
    blocked_users_list, participant_list, org_members_list,
    participant_detail, card_list_for_delete, format_card,
)

router = Router()
SUPER_ADMIN_ID = int(os.environ.get("SUPER_ADMIN", 0))


def is_super_admin(user_id: int) -> bool:
    return user_id == SUPER_ADMIN_ID


# ========================
# /admin — Super admin panel
# ========================

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("Super Admin panel:", reply_markup=super_admin_menu())


@router.callback_query(F.data == "sa_back")
async def cb_sa_back(callback: CallbackQuery, state: FSMContext):
    if not is_super_admin(callback.from_user.id):
        return
    await state.clear()
    await callback.message.edit_text("Super Admin panel:", reply_markup=super_admin_menu())


# ========================
# Barcha jamoalar
# ========================

@router.callback_query(F.data == "sa_all_orgs")
async def cb_sa_all_orgs(callback: CallbackQuery, state: FSMContext):
    if not is_super_admin(callback.from_user.id):
        return
    await state.clear()
    orgs = await db.get_all_orgs()
    if not orgs:
        await callback.message.edit_text(
            "Jamoalar yo'q.", reply_markup=super_admin_menu()
        )
        return
    await callback.message.edit_text(
        "Barcha jamoalar:", reply_markup=sa_org_list(orgs)
    )


@router.callback_query(F.data.startswith("sa_org:"))
async def cb_sa_org_detail(callback: CallbackQuery, state: FSMContext):
    if not is_super_admin(callback.from_user.id):
        return
    await state.clear()
    org_id = int(callback.data.split(":")[1])
    org = await db.get_org(org_id)
    if not org:
        await callback.answer("Jamoa topilmadi")
        return
    await callback.message.edit_text(
        f"Jamoa: {org['name']}\n"
        f"Unique ID: `{org['unique_id']}`\n"
        f"Owner ID: `{org['owner_id']}`",
        parse_mode="Markdown",
        reply_markup=sa_org_detail(org_id)
    )


@router.callback_query(F.data.startswith("sa_participants:"))
async def cb_sa_participants(callback: CallbackQuery):
    if not is_super_admin(callback.from_user.id):
        return
    org_id = int(callback.data.split(":")[1])
    participants = await db.get_participants(org_id)
    if not participants:
        await callback.message.edit_text(
            "Ishtirokchilar yo'q.",
            reply_markup=sa_org_detail(org_id)
        )
        return
    await callback.message.edit_text(
        "Ishtirokchilar:",
        reply_markup=participant_list(participants, org_id)
    )


@router.callback_query(F.data.startswith("sa_members:"))
async def cb_sa_members(callback: CallbackQuery):
    if not is_super_admin(callback.from_user.id):
        return
    org_id = int(callback.data.split(":")[1])
    members = await db.get_org_members(org_id)
    if not members:
        await callback.message.edit_text(
            "A'zolar yo'q.",
            reply_markup=sa_org_detail(org_id)
        )
        return
    await callback.message.edit_text(
        f"A'zolar ({len(members)} ta):",
        reply_markup=org_members_list(members, org_id)
    )


@router.callback_query(F.data.startswith("sa_delete_org:"))
async def cb_sa_delete_org(callback: CallbackQuery):
    if not is_super_admin(callback.from_user.id):
        return
    org_id = int(callback.data.split(":")[1])
    await db.delete_org(org_id)
    await callback.answer("Jamoa o'chirildi!")
    orgs = await db.get_all_orgs()
    if not orgs:
        await callback.message.edit_text(
            "Jamoalar yo'q.", reply_markup=super_admin_menu()
        )
    else:
        await callback.message.edit_text(
            "Barcha jamoalar:", reply_markup=sa_org_list(orgs)
        )


# ========================
# Bloklangan userlar
# ========================

@router.callback_query(F.data == "sa_blocked_users")
async def cb_sa_blocked_users(callback: CallbackQuery, state: FSMContext):
    if not is_super_admin(callback.from_user.id):
        return
    await state.clear()
    users = await db.get_blocked_users()
    if not users:
        await callback.message.edit_text(
            "Bloklangan userlar yo'q.", reply_markup=super_admin_menu()
        )
        return
    await callback.message.edit_text(
        "Bloklangan userlar (blokdan yechish uchun bosing):",
        reply_markup=blocked_users_list(users)
    )


@router.callback_query(F.data.startswith("sa_unblock:"))
async def cb_sa_unblock(callback: CallbackQuery):
    if not is_super_admin(callback.from_user.id):
        return
    telegram_id = int(callback.data.split(":")[1])
    await db.unblock_user(telegram_id)
    await callback.answer("User blokdan yechildi!")

    users = await db.get_blocked_users()
    if not users:
        await callback.message.edit_text(
            "Bloklangan userlar yo'q.", reply_markup=super_admin_menu()
        )
    else:
        await callback.message.edit_text(
            "Bloklangan userlar (blokdan yechish uchun bosing):",
            reply_markup=blocked_users_list(users)
        )


# ========================
# User bloklash
# ========================

@router.callback_query(F.data == "sa_block_user")
async def cb_sa_block_user(callback: CallbackQuery, state: FSMContext):
    if not is_super_admin(callback.from_user.id):
        return
    await state.set_state(BlockUser.telegram_id)
    await callback.message.edit_text("Bloklash uchun user Telegram ID sini kiriting:")


@router.message(BlockUser.telegram_id)
async def process_block_user(message: Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("Xato! Telegram ID raqamlardan iborat bo'lishi kerak. Qayta kiriting:")
        return
    telegram_id = int(text)
    if telegram_id == SUPER_ADMIN_ID:
        await message.answer("O'zingizni bloklash mumkin emas!", reply_markup=super_admin_menu())
        await state.clear()
        return
    await db.block_user(telegram_id)
    await state.clear()
    await message.answer(
        f"User `{telegram_id}` bloklandi!",
        parse_mode="Markdown",
        reply_markup=super_admin_menu()
    )
