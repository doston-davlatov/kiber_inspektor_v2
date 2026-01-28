import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from config import config
from db import db  # Keyinroq yoziladi
from middlewares.rate_limiter import RateLimiter  # Keyinroq yoziladi
from handlers.user_handlers import router as user_router  # Keyinroq yoziladi
from handlers.admin_handlers import router as admin_router  # Keyinroq yoziladi
from handlers.support_handlers import router as support_router  # Keyinroq yoziladi
from handlers.group_handlers import router as group_router  # Keyinroq yoziladi

# Logging sozlamalari
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL), format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def on_startup(dispatcher: Dispatcher):
    """Bot ishga tushganda ishlaydi."""
    await db.initialize()
    os.makedirs(config.TEMP_DIR, exist_ok=True)  # Temp papka yaratish
    logger.info("✅ Bot ishga tushdi va DB ulandi")

async def on_shutdown(dispatcher: Dispatcher):
    """Bot to'xtatilganda ishlaydi."""
    await db.close()
    logger.info("✅ Bot to'xtadi va DB yopildi")

async def error_handler(event, *args, **kwargs):
    """Global xato handler."""
    logger.exception("Xato yuz berdi!")
    # Foydalanuvchiga xabar yuborish mumkin

async def main():
    bot = Bot(token=config.BOT_TOKEN, parse_mode=ParseMode.HTML)
    storage = MemoryStorage()  # FSM uchun
    dp = Dispatcher(storage=storage)
    
    # Middleware qo'shish
    dp.message.middleware(RateLimiter())
    
    # Routerlarni include qilish
    dp.include_routers(user_router, admin_router, support_router, group_router)
    
    # Startup va shutdown register
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    dp.errors.register(error_handler)
    
    if config.WEBHOOK_URL:
        # Webhook mode (deploy uchun)
        from aiogram.methods import SetWebhook
        await bot.set_webhook(config.WEBHOOK_URL)
        logger.info(f"Webhook o'rnatildi: {config.WEBHOOK_URL}")
        # Webhook serverni ishga tushirish kerak (masalan, aiohttp orqali)
    else:
        # Polling mode (local test uchun)
        await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())