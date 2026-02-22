# middlewares/rate_limiter.py
"""
Rate Limiter Middleware: Foydalanuvchi so'rovlarini cheklash (anti-spam va DoS himoyasi).
Har bir foydalanuvchi uchun config.RATE_LIMIT ta so'rov/minut.

Xususiyatlar:
- Har bir foydalanuvchi uchun alohida hisoblagich
- 60 soniya ichidagi so'rovlar hisoblanadi
- Cheklov oshganda javob qaytariladi va handler chaqirilmaydi
- Logging orqali kuzatuv
- TelegramObject va Message turini to'g'ri qayta ishlash
"""

import time
from collections import defaultdict
from typing import Callable, Dict, Any, Awaitable, Optional
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from config import config
import logging

logger = logging.getLogger(__name__)

class RateLimiterMiddleware(BaseMiddleware):
    """
    Aiogram 3.x uchun rate limiter middleware.
    Foydalanuvchilarning xabar yuborish tezligini cheklaydi.
    """

    def __init__(self):
        # user_id → [timestamp1, timestamp2, ...]  (oxirgi 60 soniya ichidagi so'rovlar)
        self.user_requests: Dict[int, list[float]] = defaultdict(list)
        self.window_seconds: int = 60  # cheklov oynasi (sekund)
        self.max_requests: int = config.RATE_LIMIT

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Middleware asosiy metod.
        Faqat Message turidagi eventlarni cheklaydi.
        """
        # Agar xabar bo'lmasa (callback_query, inline_query va h.k.) → cheklovsiz o'tkazamiz
        if not isinstance(event, Message):
            return await handler(event, data)

        # Botning o'z xabarlari yoki kanal xabarlari uchun cheklov qo'llamaymiz
        if event.from_user is None or event.from_user.is_bot:
            return await handler(event, data)

        user_id = event.from_user.id
        now = time.time()

        # Eski so'rovlarini tozalash (window_seconds dan eski bo'lganlarni o'chirish)
        self.user_requests[user_id] = [
            t for t in self.user_requests[user_id]
            if now - t < self.window_seconds
        ]

        # Hozirgi so'rovlar sonini tekshirish
        current_count = len(self.user_requests[user_id])

        if current_count >= self.max_requests:
            # Cheklov oshdi → javob beramiz va handler chaqirilmaydi
            try:
                await event.reply(
                    f"⚠️ Tez yozmoqdasiz!\n"
                    f"Cheklov: {self.max_requests} ta xabar / {self.window_seconds} soniya.\n"
                    f"Iltimos, {int(self.window_seconds - (now - self.user_requests[user_id][0]))} soniya kuting."
                )
            except Exception as reply_err:
                logger.warning(f"Rate limit javob yuborishda xato: {reply_err}")

            logger.warning(
                f"Rate limit oshdi | user_id={user_id} | "
                f"so'rovlar={current_count}/{self.max_requests} | chat_id={event.chat.id}"
            )
            return  # handler chaqirilmaydi

        # So'rovni qayd etamiz va keyingi handlerga o'tkazamiz
        self.user_requests[user_id].append(now)

        # Qo'shimcha logging (debug rejimida)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"User {user_id} so'rovi qayd etildi | "
                f"hozirgi: {current_count + 1}/{self.max_requests}"
            )

        return await handler(event, data)


# Global instance (main.py da ishlatish uchun)
rate_limiter_middleware = RateLimiterMiddleware()