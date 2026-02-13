import os
import asyncio
import logging

from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

import db
from handlers import admin, user, inline

BOT_TOKEN = os.environ["BOT_TOKEN"]
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")
PORT = int(os.environ.get("PORT", 10000))
IS_RENDER = bool(RENDER_URL)  # Render o'zi RENDER_EXTERNAL_URL beradi

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

dp.include_router(admin.router)
dp.include_router(user.router)
dp.include_router(inline.router)

logging.basicConfig(level=logging.INFO)


# --- Webhook (Render) ---

async def on_startup_webhook(app):
    await db.init_db()
    webhook_url = f"{RENDER_URL}/webhook"
    await bot.set_webhook(webhook_url)
    logging.info(f"Webhook set: {webhook_url}")


async def on_shutdown_webhook(app):
    await db.close_db()
    await bot.session.close()


def run_webhook():
    app = web.Application()
    app.on_startup.append(on_startup_webhook)
    app.on_shutdown.append(on_shutdown_webhook)

    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)

    web.run_app(app, host="0.0.0.0", port=PORT)


# --- Polling (lokal) ---

async def run_polling():
    await db.init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Polling mode started")
    try:
        await dp.start_polling(bot)
    finally:
        await db.close_db()
        await bot.session.close()


if __name__ == "__main__":
    if IS_RENDER:
        run_webhook()
    else:
        asyncio.run(run_polling())
