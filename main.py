import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from db import db
import nltk

from handlers import router
from middlewares import rate_limiter_middleware

# Agar logging_middleware mavjud bo'lsa import qiling
# from middlewares.logging import logging_middleware
# Agar yo'q bo'lsa quyidagi qatorni komment qiling yoki o'chirib tashlang

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

WEBHOOK_PATH = "/webhook/"

# WEBHOOK_URL ni xavfsiz qayta ishlash
webhook_base = config.WEBHOOK_URL or ""
WEBHOOK_URL = f"{webhook_base.rstrip('/')}{WEBHOOK_PATH}" if webhook_base else None

WEBHOOK_SECRET = config.WEBHOOK_SECRET or "kiber-inspektor-secret-2025"

async def on_startup(bot: Bot):
    logger.info("on_startup boshlandi")
    await db.initialize()
    
    try:
        nltk.download('punkt', quiet=True)
        nltk.download('stopwords', quiet=True)
        logger.info("NLTK ma'lumotlari yuklandi")
    except Exception as e:
        logger.warning(f"NLTK download xatosi: {e}")

    if WEBHOOK_URL:
        try:
            await bot.set_webhook(
                url=WEBHOOK_URL,
                secret_token=WEBHOOK_SECRET,
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query", "my_chat_member"]
            )
            logger.info(f"Webhook muvaffaqiyatli o'rnatildi: {WEBHOOK_URL}")
        except Exception as e:
            logger.error(f"Webhook o'rnatishda xato: {e}", exc_info=True)
    else:
        logger.warning("WEBHOOK_URL sozlanmagan → webhook o'rnatilmaydi")


async def on_shutdown(bot: Bot):
    logger.info("on_shutdown boshlandi")
    if WEBHOOK_URL:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Webhook o'chirildi")
        except Exception as e:
            logger.warning(f"Webhook o'chirishda xato: {e}")
    
    await db.close()
    logger.info("DB ulanishi yopildi")


async def main():
    try:
        bot = Bot(
            token=config.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode="HTML")
        )
        logger.info("Bot obyekti yaratildi")

        dp = Dispatcher(storage=MemoryStorage())
        logger.info("Dispatcher yaratildi")

        # Middleware'larni ulash
        # Agar logging_middleware mavjud bo'lsa:
        # dp.message.middleware(logging_middleware)
        
        dp.message.middleware(rate_limiter_middleware)
        logger.info("Middleware'lar ulandi")

        dp.include_router(router)
        logger.info("Router qo'shildi")

        app = web.Application()
        webhook_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            secret_token=WEBHOOK_SECRET,
        )
        webhook_handler.register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)
        logger.info("Aiohttp application tayyorlandi")

        app.on_startup.append(lambda _: asyncio.create_task(on_startup(bot)))
        app.on_shutdown.append(lambda _: asyncio.create_task(on_shutdown(bot)))

        runner = web.AppRunner(app)
        await runner.setup()
        logger.info("Runner setup bo'ldi")

        port = int(os.getenv("PORT", 10000))
        host = "0.0.0.0"

        site = web.TCPSite(runner, host=host, port=port)
        await site.start()
        logger.info(f"Server ishga tushdi → {host}:{port}{WEBHOOK_PATH}")
        logger.info(f"Render PORT qiymati: {os.getenv('PORT', 'topilmadi')}")

        await asyncio.Event().wait()

    except Exception as e:
        logger.error("main() funksiyasida xato", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi (KeyboardInterrupt yoki SystemExit)")
    except Exception as e:
        logger.error(f"Dastur ishga tushmadi: {e}", exc_info=True)