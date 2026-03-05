from aiogram import Router, F
from aiogram.types import Message
from db import db
from keyboards.main_keyboard import get_main_keyboard, get_mode_selection_keyboard

router = Router(name="mode_handlers")

@router.message(F.text.in_({"/check", "/scanurl", "/support", "Fayl yuborish",
                           "🔍 To'liq tekshirish", "🔗 Faqat havola",
                           "📄 Fayl tekshirish", "⛔ Tekshirishni to'xtatish"}))
async def set_scan_mode(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    if text in ("/check", "🔍 To'liq tekshirish"):
        mode = "full_check"
        reply = "✅ Endi har qanday xabaringiz (matn, havola, fayl) to‘liq tekshiriladi."
    elif text in ("/scanurl", "🔗 Faqat havola"):
        mode = "url_only"
        reply = "✅ Endi faqat havolalarni tekshiraman."
    elif text in ("/support",):
        mode = "support"
        reply = "✅ Support rejimi yoqildi. Savolingizni yozing."
    elif text in ("Fayl yuborish", "📄 Fayl tekshirish"):
        mode = "file_scan"
        reply = "✅ Fayl yuboring — VirusTotal orqali tekshiriladi."
    elif text == "⛔ Tekshirishni to'xtatish":
        mode = "none"
        reply = "✅ Tekshirish to‘xtatildi."
    else:
        return

    await db.set_user_mode(user_id, mode)
    await message.answer(reply, reply_markup=get_mode_selection_keyboard() if mode != "none" else get_main_keyboard())