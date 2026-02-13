import os
import logging

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

import db
from handlers import admin, user, inline

BOT_TOKEN = os.environ["BOT_TOKEN"]
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")
PORT = int(os.environ.get("PORT", 10000))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

dp.include_router(admin.router)
dp.include_router(user.router)
dp.include_router(inline.router)

logging.basicConfig(level=logging.INFO)


async def on_startup(app):
    await db.init_db()
    webhook_url = f"{RENDER_URL}/webhook"
    await bot.set_webhook(webhook_url)
    logging.info(f"Webhook set: {webhook_url}")


async def on_shutdown(app):
    await db.close_db()
    await bot.session.close()


def main():
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)

    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
