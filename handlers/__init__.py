# handlers/__init__.py
"""
Handlers moduli: turli xil komanda va xabar turlarini qayta ishlovchi routerlar.
"""

from .user_handlers import router as user_router
from .admin_handlers import router as admin_router
from .support_handlers import router as support_router
from .group_handlers import router as group_router

__all__ = [
    "user_router",
    "admin_router",
    "support_router",
    "group_router",
]