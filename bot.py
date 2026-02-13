import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

BOT_TOKEN = os.environ["BOT_TOKEN"]
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")
PORT = int(os.environ.get("PORT", 10000))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)


@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("Salom! Menga text yuboring, men saqlab qo'yaman.")


@dp.message()
async def save_text(message: types.Message):
    # Textni faylga saqlash
    with open("saved_texts.txt", "a", encoding="utf-8") as f:
        f.write(f"{message.from_user.id}: {message.text}\n")
    await message.answer("Saqlandi!")


async def on_startup(app):
    webhook_url = f"{RENDER_URL}/webhook"
    await bot.set_webhook(webhook_url)
    logging.info(f"Webhook set: {webhook_url}")


def main():
    app = web.Application()
    app.on_startup.append(on_startup)

    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)

    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
