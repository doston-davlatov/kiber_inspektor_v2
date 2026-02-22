# middlewares/logging.py
from aiogram import BaseMiddleware
import logging

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if hasattr(event, 'from_user') and event.from_user:
            logger.info(f"User {event.from_user.id} → {event.text or '[no text]'}")
        return await handler(event, data)

logging_middleware = LoggingMiddleware()