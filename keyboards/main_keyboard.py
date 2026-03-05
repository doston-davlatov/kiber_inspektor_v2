from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

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

def get_mode_selection_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🔍 To'liq tekshirish"), KeyboardButton(text="🔗 Faqat havola"))
    builder.row(KeyboardButton(text="📄 Fayl tekshirish"), KeyboardButton(text="⛔ Tekshirishni to'xtatish"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)