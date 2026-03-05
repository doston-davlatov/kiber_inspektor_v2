# main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from db import db
import nltk

from handlers import router
from middlewares import rate_limiter_middleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def on_startup(bot: Bot):
    logger.info("Bot ishga tushmoqda (polling)")
    await db.initialize()
    
    try:
        nltk.download('punkt', quiet=True)
        nltk.download('punkt_tab', quiet=True)
        nltk.download('stopwords', quiet=True)
    except Exception as e:
        logger.warning(f"NLTK yuklashda xato: {e}")

    logger.info("Polling rejimi boshlandi")

async def on_shutdown(bot: Bot):
    logger.info("Bot to'xtamoqda")
    await db.close()
    logger.info("DB ulanishi yopildi")

async def main():
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook o'chirildi (agar mavjud bo'lsa)")
    
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(rate_limiter_middleware)
    dp.include_router(router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await dp.start_polling(
        bot,
        allowed_updates=["message", "callback_query", "my_chat_member"],
        drop_pending_updates=True
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi")
    except Exception as e:
        logger.error(f"Dastur ishga tushmadi: {e}", exc_info=True)