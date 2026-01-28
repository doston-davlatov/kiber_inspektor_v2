# handlers/group_handlers.py
"""
Guruh monitoringi: har bir xabarni avtomatik tahlil qilish,
xavfli bo'lsa ogohlantirish yoki botni ban qilish.
"""

import logging
import asyncio
from typing import Optional
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import ChatTypeFilter

from analyzers import analyze_text, scan_url, scan_file
from db import db
from config import config
from utils.helpers import cleanup_temp_file

logger = logging.getLogger(__name__)

router = Router(name="group_handlers")

# Faqat guruh va superguruhlar uchun ishlaydi
router.message.filter(ChatTypeFilter(chat_types=["group", "supergroup"]))

@router.message()
async def group_message_handler(message: Message):
    """
    Guruhdagi har bir xabarni tekshirish:
    - Matn bo'lsa: scam/phishing aniqlash
    - Havola bo'lsa: URL skan
    - Fayl bo'lsa: fayl skan
    Xavfli bo'lsa: ogohlantirish va loglash
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text or message.caption or ""

    # 1. Foydalanuvchi va guruhni DB ga qo'shish
    await db.add_user(user_id, message.from_user.username, message.from_user.full_name)
    await db.add_group(chat_id, message.chat.title or "Noma'lum guruh")

    threat_level = "Safe"
    reason = ""
    is_file = False

    try:
        # Fayl mavjud bo'lsa (rasm, video, hujjat va h.k.)
        document = message.document or message.photo[-1] if message.photo else \
                   message.video or message.audio or message.voice

        if document:
            is_file = True
            file_size = document.file_size
            if file_size > config.MAX_FILE_SIZE:
                await message.reply("⚠️ Fayl juda katta, tekshirib bo'lmaydi!")
                return

            await message.reply("📁 Fayl tekshirilmoqda...")

            file_info = await message.bot.get_file(document.file_id)
            downloaded_file = await message.bot.download_file(file_info.file_path)

            temp_path = f"temp/{document.file_id}_{document.file_name or 'file'}"
            with open(temp_path, "wb") as f:
                f.write(downloaded_file.read())

            result = await scan_file(temp_path)
            threat_level = result["threat"]
            reason = result["reason"]

            cleanup_temp_file(temp_path)

        # Matn yoki caption mavjud bo'lsa
        elif text:
            # URL borligini tekshirish
            urls = re.findall(r'(https?://[^\s]+)', text)
            if urls:
                await message.reply("🔗 Havola tekshirilmoqda...")
                for url in urls:
                    url_result = await scan_url(url)
                    if url_result["threat"] in ["Low", "High"]:
                        threat_level = url_result["threat"]
                        reason += f"\nHavola: {url} → {url_result['reason']}"

            # Matnni scam uchun tahlil
            text_result = analyze_text(text)
            if text_result["threat"] in ["Low", "High"]:
                threat_level = text_result["threat"]
                reason += f"\nMatn tahlili: {text_result['reason']}"

        # Yakuniy harakat
        if threat_level != "Safe":
            emoji = "🟡" if threat_level == "Low" else "🔴"
            warning_text = (
                f"{emoji} <b>Xavfli xabar aniqlandi!</b>\n"
                f"• Daraja: {threat_level}\n"
                f"• Sabab: {reason}\n"
                f"• Foydalanuvchi: @{message.from_user.username or message.from_user.id}\n"
                f"• Xabar: {text[:150]}{'...' if len(text) > 150 else ''}"
            )
            await message.reply(warning_text, disable_web_page_preview=True)

            # Loglash
            await db.log_message(
                group_id=chat_id,
                user_id=user_id,
                text=text or "[Fayl]",
                threat_level=threat_level
            )

            # Agar xavf yuqori bo'lsa va auto-ban yoqilgan bo'lsa (config da)
            # if threat_level == "High" and config.AUTO_BAN_ENABLED:
            #     await message.bot.ban_chat_member(chat_id, user_id)
            #     await message.reply(f"🚫 {message.from_user.first_name} ban qilindi!")

    except Exception as e:
        logger.error(f"Guruh monitoring xatosi: {e}", exc_info=True)
        # Foydalanuvchiga xabar bermaymiz, faqat loglaymiz