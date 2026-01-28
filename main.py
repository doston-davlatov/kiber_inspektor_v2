import asyncio
import logging
import os  # 1. os moduli qo'shildi (makedirs uchun)
import nltk
from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties  # 2. Yangi versiya uchun kerak

from config import config
from db import db 
from middlewares.rate_limiter import RateLimiter 
from handlers.user_handlers import router as user_router 
from handlers.admin_handlers import router as admin_router 
from handlers.support_handlers import router as support_router 
from handlers.group_handlers import router as group_router 

# Logging sozlamalari
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL), 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def on_startup(bot: Bot):  # Aiogram 3 da bot ob'ekti argument sifatida kelishi mumkin
    """Bot ishga tushganda ishlaydi."""
    await db.initialize()
    os.makedirs(config.TEMP_DIR, exist_ok=True)  # Temp papka yaratish
    logger.info("✅ Bot ishga tushdi va DB ulandi")

async def on_shutdown(bot: Bot):
    """Bot to'xtatilganda ishlaydi."""
    await db.close()
    logger.info("✅ Bot to'xtadi va DB yopildi")

async def error_handler(event, exception):
    """Global xato handler."""
    logger.exception(f"Xato yuz berdi: {exception}")

async def main():
    # 3. Botni yangi DefaultBotProperties bilan yaratish
    bot = Bot(
        token=config.BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Middleware qo'shish
    dp.message.middleware(RateLimiter())
    
    # Routerlarni include qilish
    dp.include_routers(user_router, admin_router, support_router, group_router)
    
    # Startup va shutdown register
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    dp.errors.register(error_handler)
    
    try:
        if config.WEBHOOK_URL:
            # Webhook mode
            await bot.set_webhook(config.WEBHOOK_URL)
            logger.info(f"Webhook o'rnatildi: {config.WEBHOOK_URL}")
            # Webhook serverni bu yerda ishga tushirish (masalan, aiohttp)
        else:
            # Polling mode
            logger.info("Bot polling rejimida ishga tushmoqda...")
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot qo'lda to'xtatildi")