"""
Guruh monitoringi: har bir xabarni avtomatik tahlil qilish,
xavfli bo'lsa ogohlantirish.
"""

import logging
import asyncio
import re  # 1. re moduli qo'shildi
from typing import Optional
from aiogram import Router, F, types
from aiogram.types import Message

# analyzers moduli ichidagi funksiyalar mavjudligini tekshiring
from analyzers import analyze_text, scan_url, scan_file
from db import db
from config import config
from utils.helpers import cleanup_temp_file

logger = logging.getLogger(__name__)

router = Router(name="group_handlers")

# 2. Aiogram 3 uchun filtr o'zgartirildi
@router.message(F.chat.type.in_({"group", "supergroup"}))
async def group_message_handler(message: Message):
    """
    Guruhdagi har bir xabarni tekshirish.
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text or message.caption or ""

    # 1. Foydalanuvchi va guruhni DB ga qo'shish
    await db.add_user(user_id, message.from_user.username, message.from_user.full_name)
    await db.add_group(chat_id, message.chat.title or "Noma'lum guruh")

    threat_level = "Safe"
    reason = ""

    try:
        # Fayl mavjud bo'lsa
        document = message.document or (message.photo[-1] if message.photo else None) or \
                   message.video or message.audio or message.voice

        if document and hasattr(document, 'file_id'):
            file_size = getattr(document, 'file_size', 0)
            if file_size > config.MAX_FILE_SIZE:
                await message.reply("⚠️ Fayl juda katta, tekshirib bo'lmaydi!")
                return

            status_msg = await message.reply("📁 Fayl tekshirilmoqda...")

            file_info = await message.bot.get_file(document.file_id)
            
            # Faylni saqlash uchun yo'l
            file_name = getattr(document, 'file_name', f"file_{document.file_id}")
            temp_path = f"{config.TEMP_DIR}/{document.file_id}_{file_name}"
            
            # 3. Faylni to'g'ri yuklab olish
            await message.bot.download_file(file_info.file_path, destination=temp_path)

            result = await scan_file(temp_path)
            threat_level = result["threat"]
            reason = result["reason"]

            cleanup_temp_file(temp_path)
            await status_msg.delete()

        # Matn yoki caption mavjud bo'lsa
        if text:
            # URL borligini tekshirish
            urls = re.findall(r'(https?://[^\s]+)', text)
            if urls:
                status_msg = await message.reply("🔗 Havola tekshirilmoqda...")
                for url in urls:
                    url_result = await scan_url(url)
                    if url_result["threat"] in ["Low", "High"]:
                        threat_level = url_result["threat"]
                        reason += f"\nHavola: {url} → {url_result['reason']}"
                await status_msg.delete()

            # Matnni scam uchun tahlil
            text_result = analyze_text(text)
            if text_result["threat"] in ["Low", "High"]:
                if threat_level != "High": # High darajani tushirmaslik uchun
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
            await message.reply(warning_text, parse_mode="HTML")

            # Loglash
            await db.log_message(
                group_id=chat_id,
                user_id=user_id,
                text=text or "[Fayl]",
                threat_level=threat_level
            )

    except Exception as e:
        logger.error(f"Guruh monitoring xatosi: {e}", exc_info=True)