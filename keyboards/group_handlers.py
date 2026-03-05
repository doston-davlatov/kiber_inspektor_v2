import logging
from aiogram import Router, F
from aiogram.types import Message
from analyzers.image_analyzer import analyze_image
from db import db
from analyzers import analyze_text, scan_url, scan_file
from handlers.group_handlers import scan_message
from keyboards.main_keyboard import get_main_keyboard
from utils.helpers import cleanup_temp_file
from config import config

logger = logging.getLogger(__name__)
router = Router(name="group_handlers")

@router.message()
async def smart_scan_handler(message: Message):
    user_id = message.from_user.id
    chat_type = message.chat.type
    if chat_type in {"group", "supergroup", "channel"}:
        await scan_message(message)
        return
    mode = await db.get_user_mode(user_id)

    if mode == "none" or not mode:
        await message.answer(
            "Iltimos, pastdagi tugmalardan birini bosing:",
            reply_markup=get_main_keyboard()
        )
        return
    should_scan = False


    if message.photo:
        photo = message.photo[-1]
        file_info = await message.bot.get_file(photo.file_id)
        temp_path = config.TEMP_DIR / f"photo_{photo.file_id}.jpg"
        
        await message.bot.download_file(file_info.file_path, temp_path)
        
        image_result = await analyze_image(temp_path)
        
        if image_result["threat"] != "Safe":
            threat_level = max(threat_level, image_result["threat"], key=lambda x: {"Safe":0, "Low":1, "High":2}[x])
            reason_parts.append(f"Rasm tahlili: {image_result['reason']}")
        
        cleanup_temp_file(str(temp_path))
            
    if mode == "full_check":
        should_scan = True
    elif mode == "url_only":
        text = message.text or message.caption or ""
        if "http" in text.lower():
            should_scan = True
    elif mode == "file_scan":
        if message.document or message.photo or message.video:
            should_scan = True
    elif mode == "support":
        await message.answer("Savolingiz qabul qilindi. Tez orada javob beramiz.")
        return

    if should_scan:
        await scan_message(message) 
    else:
        await message.answer("Bu rejimda faqat tanlangan turdagi kontentni qabul qilaman.")