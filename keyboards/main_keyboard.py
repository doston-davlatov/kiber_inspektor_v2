# keyboards/main_keyboard.py
"""
Inline va ReplyKeyboardMarkup tugmalari yaratish funksiyalari.
"""

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestUsers,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from config import config

def get_main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """
    Oddiy foydalanuvchilar uchun asosiy Reply keyboard.
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="/check"),
        KeyboardButton(text="/scanurl"),
    )
    builder.row(
        KeyboardButton(text="/support"),
        KeyboardButton(text="Fayl yuborish"),
    )

    if is_admin:
        builder.row(
            KeyboardButton(text="/stats"),
            KeyboardButton(text="/requests"),
        )

    builder.adjust(2)

    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Komanda yoki fayl yuboring...",
        one_time_keyboard=False
    )


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """
    Admin uchun inline tugmalar (statistika, ban va boshqalar).
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📊 Yangi statistika", callback_data="admin_stats"),
        InlineKeyboardButton(text="⚠️ Oxirgi xavflar", callback_data="admin_recent_threats"),
    )
    builder.row(
        InlineKeyboardButton(text="🔍 Foydalanuvchi qidirish", callback_data="admin_search_user"),
    )

    builder.adjust(2)

    return builder.as_markup()


def get_support_keyboard(requests: list) -> InlineKeyboardMarkup:
    """
    Admin uchun support so'rovlariga inline tugmalar.
    Har bir so'rov uchun "Ko'rish" va "Yopish" tugmalari.
    """
    builder = InlineKeyboardBuilder()

    for req in requests[:5]:  # Ko'pi bilan 5 ta ko'rsatamiz
        builder.row(
            InlineKeyboardButton(
                text=f"ID {req['id']} - Ko'rish",
                callback_data=f"support_view_{req['id']}"
            ),
            InlineKeyboardButton(
                text="Yopish",
                callback_data=f"support_close_{req['id']}"
            ),
        )
        builder.row(
            InlineKeyboardButton(
                text="Javob berish",
                callback_data=f"support_reply_{req['id']}"
            ),
        )

    if len(requests) > 5:
        builder.row(InlineKeyboardButton(text="Barchasini ko'rish", callback_data="support_all"))

    builder.adjust(2)

    return builder.as_markup()


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    FSM jarayonlarida "Bekor qilish" tugmasi.
    """
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="❌ Bekor qilish"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)