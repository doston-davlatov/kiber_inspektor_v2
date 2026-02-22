# middlewares/__init__.py
"""
Middlewares moduli: botga global qo'shimcha logika qo'shish uchun middleware'lar.
Hozircha faqat rate limiter mavjud, kelajakda quyidagilar qo'shilishi mumkin:
- LoggingMiddleware (har bir xabarni loglash)
- ValidationMiddleware (xabar tarkibini tekshirish)
- AuthMiddleware (admin/foydalanuvchi ruxsatlarini tekshirish)
- AntiFloodMiddleware (vaqtinchalik cheklovlar)
"""

# Asosiy eksport qilinadigan ob'ektlar
from .rate_limiter import rate_limiter_middleware

# Kelajakda qo'shilishi mumkin bo'lgan middleware'larni shu yerga import qilish mumkin
# from .logging import logging_middleware
# from .validation import validation_middleware
# from .auth import admin_only_middleware

# Eksport qilinadigan nomlar (main.py da ishlatish uchun qulay)
__all__ = [
    "rate_limiter_middleware",          # asosiy rate limiter instance
    "logging_middleware",             # kelajakda
    # "validation_middleware",
    # "admin_only_middleware",
]