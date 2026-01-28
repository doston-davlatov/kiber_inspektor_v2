# middlewares/__init__.py
"""
Middlewares moduli: botga global qo'shimcha logika qo'shish.
Hozircha faqat rate limiter mavjud, kelajakda validation, logging middleware qo'shilishi mumkin.
"""
from .rate_limiter import RateLimiter
__all__ = [
    "RateLimiter",
]