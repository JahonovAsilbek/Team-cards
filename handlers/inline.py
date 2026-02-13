import os

from aiogram import Router
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

import db
from keyboards import format_card

router = Router()
SUPER_ADMIN_ID = int(os.environ.get("SUPER_ADMIN", 0))


@router.inline_query()
async def inline_handler(query: InlineQuery):
    # Bloklangan user
    if await db.is_blocked(query.from_user.id):
        await query.answer(results=[], cache_time=5)
        return

    is_super = query.from_user.id == SUPER_ADMIN_ID

    if is_super:
        # Super admin barcha tashkilotlarni ko'radi
        participants = await db.get_all_participants()
    else:
        # Oddiy user — a'zo bo'lgan tashkilotlardan
        participants = await db.get_participants_for_user(query.from_user.id)

    if not participants:
        await query.answer(
            results=[
                InlineQueryResultArticle(
                    id="empty",
                    title="Ishtirokchilar yo'q",
                    description="Jamoaga ulanib, ishtirokchi qo'shing",
                    input_message_content=InputTextMessageContent(
                        message_text="Hozircha ishtirokchilar yo'q.",
                    ),
                )
            ],
            cache_time=5,
        )
        return

    search = query.query.strip().lower()
    results = []

    for p in participants:
        if search and search not in p["fio"].lower():
            continue

        cards = await db.get_cards(p["id"])
        if not cards:
            continue

        cards_text = "\n".join(
            f"`{format_card(c['card_number'])}`" for c in cards
        )

        # Preview: FIO (Tashkilot nomi)
        title = f"{p['fio']} ({p['org_name']})"
        # Xabar: faqat FIO + kartalar
        message_text = f"{p['fio']}\n{cards_text}"

        results.append(
            InlineQueryResultArticle(
                id=str(p["id"]),
                title=title,
                description=f"{len(cards)} ta karta",
                input_message_content=InputTextMessageContent(
                    message_text=message_text,
                    parse_mode="Markdown",
                ),
            )
        )

    await query.answer(results=results[:50], cache_time=5)
