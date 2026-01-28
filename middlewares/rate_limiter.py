# middlewares/rate_limiter.py
"""
Rate Limiter Middleware: foydalanuvchi so'rovlarini cheklash uchun (DoS hujumlariga qarshi).
Har bir foydalanuvchi uchun N ta so'rov/min.
"""

import time
from collections import defaultdict
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from config import config
import logging

logger = logging.getLogger(__name__)

class RateLimiter(BaseMiddleware):
    """
    Rate limiter middleware: user_id bo'yicha cheklov.
    """
    def __init__(self):
        self.user_requests: Dict[int, list[float]] = defaultdict(list)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Optional[Any]:
        if not isinstance(event, Message):
            return await handler(event, data)

        user_id = event.from_user.id
        now = time.time()

        # Eski so'rovlarini tozalash (1 daqiqa oldingilar)
        self.user_requests[user_id] = [t for t in self.user_requests[user_id] if now - t < 60]

        # Cheklovni tekshirish
        if len(self.user_requests[user_id]) >= config.RATE_LIMIT:
            await event.reply(
                f"⚠️ Juda ko'p so'rov! {config.RATE_LIMIT} ta/min cheklovi. 1 daqiqa kuting."
            )
            logger.warning(f"Rate limit oshdi: user {user_id}")
            return  # Handlerni chaqirmaymiz

        # So'rovni qo'shish
        self.user_requests[user_id].append(now)

        # Keyingi handlerga o'tkazish
        return await handler(event, data)