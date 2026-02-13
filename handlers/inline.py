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
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))


@router.inline_query()
async def inline_handler(query: InlineQuery):
    is_admin = query.from_user.id == ADMIN_ID

    if is_admin:
        participants = await db.get_all_participants()
    else:
        session = await db.get_user_session(query.from_user.id)
        if not session:
            await query.answer(
                results=[],
                cache_time=5,
                switch_pm_text="Avval tashkilotga ulaning",
                switch_pm_parameter="start",
            )
            return
        participants = await db.get_participants(session["org_id"])

    if not participants:
        await query.answer(results=[], cache_time=5)
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

        if is_admin:
            title = f"{p['fio']} ({p['org_name']})"
        else:
            title = p["fio"]
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
