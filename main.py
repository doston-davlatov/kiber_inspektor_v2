import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from db import init_db, close_db, create_tables
import nltk

from handlers import router
from middlewares import rate_limiter_middleware
from analyzers import text_analyzer, url_scanner, file_scanner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

WEBHOOK_PATH = "/webhook/"
WEBHOOK_URL = f"{config.WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"
WEBHOOK_SECRET = config.WEBHOOK_SECRET or "kiber-inspektor-secret-2025-random-xyz"

async def on_startup(bot: Bot):
    await create_tables()
    await init_db()
    
    try:
        nltk.download('punkt', quiet=True)
        nltk.download('stopwords', quiet=True)
    except Exception as e:
        logger.warning(f"NLTK download xatosi: {e}")

    await bot.set_webhook(
        url=WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query", "my_chat_member"]
    )
    logger.info(f"Webhook o'rnatildi: {WEBHOOK_URL}")


async def on_shutdown(bot: Bot):
    await bot.delete_webhook(drop_pending_updates=True)
    await close_db()
    logger.info("Webhook o'chirildi va bot to'xtadi")


async def main():
    bot = Bot(token=config.BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(rate_limiter_middleware)
    dp.include_router(router)

    app = web.Application()

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    )

    webhook_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    app.on_startup.append(lambda _: asyncio.create_task(on_startup(bot)))
    app.on_shutdown.append(lambda _: asyncio.create_task(on_shutdown(bot)))

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(config.WEBHOOK_PORT or 8080)

    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()

    logger.info(f"Server ishga tushdi → http://0.0.0.0:{port}{WEBHOOK_PATH}")

    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi")
    except Exception as e:
        logger.error(f"Kutilmagan xato: {e}", exc_info=True)