# keyboards/__init__.py
"""
Keyboards moduli: inline va reply tugmalarini yaratish.
"""

from .main_keyboard import (
    get_main_keyboard,
    get_admin_keyboard,
    get_support_keyboard,
)

__all__ = [
    "get_main_keyboard",
    "get_admin_keyboard",
    "get_support_keyboard",
]