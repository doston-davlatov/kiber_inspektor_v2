# keyboards/main_keyboard.py

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from config import config


def get_main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="/check"), KeyboardButton(text="/scanurl"))
    builder.row(KeyboardButton(text="/support"), KeyboardButton(text="Fayl yuborish"))
    
    if is_admin:
        builder.row(KeyboardButton(text="/stats"), KeyboardButton(text="/threats"))
    
    builder.adjust(2)
    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Komanda yoki fayl yuboring...",
        one_time_keyboard=False
    )

def get_admin_inline_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
        InlineKeyboardButton(text="⚠️ Oxirgi xavflar", callback_data="admin_threats"),
    )
    builder.row(
        InlineKeyboardButton(text="🔍 Foydalanuvchi qidirish", callback_data="admin_search_user"),
    )
    builder.row(
        InlineKeyboardButton(text="🛠 Admin panel", callback_data="admin_panel"),
    )

    builder.adjust(2)

    return builder.as_markup()


def get_support_inline_keyboard(requests: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for req in requests[:5]:
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
        builder.row(
            InlineKeyboardButton(
                text="Barcha so'rovlarni ko'rish",
                callback_data="support_all_requests"
            )
        )

    builder.adjust(2)

    return builder.as_markup()


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="❌ Bekor qilish"))
    return builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_mode_selection_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🔍 To'liq tekshirish"), KeyboardButton(text="🔗 Faqat havola"))
    builder.row(KeyboardButton(text="📄 Fayl tekshirish"), KeyboardButton(text="⛔ Tekshirishni to'xtatish"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)