# handlers/__init__.py
"""
Handlers moduli: turli xil komanda va xabar turlarini qayta ishlovchi routerlar.
Barcha handler routerlari shu yerda birlashtiriladi.
"""

from aiogram import Router

from .user_handlers import router as user_router
from .admin_handlers import router as admin_router
from .support_handlers import router as support_router
from .group_handlers import router as group_router

# Markaziy router hosil qilamiz
router = Router(name="main_router")

# Barcha sub-routerlarni markaziy routerga qo'shamiz
router.include_router(user_router)
router.include_router(admin_router)
router.include_router(support_router)
router.include_router(group_router)

# Eksport qilish uchun __all__ (ixtiyoriy, lekin yaxshi amaliyot)
__all__ = [
    "router",              # asosiy router — main.py da shu ishlatiladi
    "user_router",
    "admin_router",
    "support_router",
    "group_router",
]