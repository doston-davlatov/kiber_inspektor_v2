# handlers/group_handlers.py
import logging
import re
from typing import Optional
from aiogram import Router, F
from aiogram.types import Message

from analyzers import analyze_text, scan_url, scan_file
from db import db
from config import config
from utils.helpers import cleanup_temp_file

logger = logging.getLogger(__name__)
router = Router(name="group_handlers")

@router.message(F.chat.type.in_({"private", "group", "supergroup", "channel"}))
async def scan_message(message: Message):
    if not message.text and not message.caption and not message.document and not message.photo and not message.video:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    message_id = message.message_id
    text = message.text or message.caption or ""
    chat_type = message.chat.type
    chat_title = message.chat.title or message.chat.first_name or message.chat.username or "Private"

    await db.add_user(user_id, message.from_user.username, message.from_user.full_name)

    if chat_type in ("group", "supergroup", "channel"):
        await db.add_group(chat_id, chat_title)

    threat_level = "Safe"
    reason_parts = []

    try:
        # Fayl tekshirish
        document = message.document or message.photo[-1] if message.photo else None
        if document:
            file_size = getattr(document, 'file_size', 0)
            if file_size > config.MAX_FILE_SIZE:
                await message.reply("Fayl juda katta — tekshirib bo'lmaydi")
                return

            file_info = await message.bot.get_file(document.file_id)
            file_name = getattr(document, 'file_name', f"file_{document.file_id}")
            temp_path = config.TEMP_DIR / f"{document.file_id}_{file_name}"

            await message.bot.download_file(file_info.file_path, temp_path)
            result = await scan_file(str(temp_path))
            threat_level = result["threat"]
            if result["reason"]:
                reason_parts.append(result["reason"])
            cleanup_temp_file(str(temp_path))

        # URL tekshirish
        if text:
            urls = re.findall(r'(https?://[^\s]+)', text)
            for url in urls:
                url_result = await scan_url(url)
                if url_result["threat"] != "Safe":
                    threat_level = max(threat_level, url_result["threat"], key=lambda x: {"Safe":0, "Low":1, "High":2}[x])
                    reason_parts.append(f"Havola {url}: {url_result['reason']}")

            # Matn tahlili
            text_result = analyze_text(text)
            if text_result["threat"] != "Safe":
                threat_level = max(threat_level, text_result["threat"], key=lambda x: {"Safe":0, "Low":1, "High":2}[x])
                reason_parts.append(text_result["reason"])

        if threat_level != "Safe":
            reason = "\n".join(reason_parts) or "Aniqlangan xavf"
            emoji = "🟡" if threat_level == "Low" else "🔴"

            warning = (
                f"{emoji} Xavf aniqlandi!\n"
                f"Daraja: {threat_level}\n"
                f"Sabab:\n{reason}\n"
                f"Foydalanuvchi: {message.from_user.mention_html()}"
            )
            await message.reply(warning, parse_mode="HTML")

            await db.log_threat(
                chat_id=chat_id,
                message_id=message_id,
                user_id=user_id,
                text=text,
                threat_level=threat_level,
                reason=reason,
                chat_type=chat_type,
                chat_title=chat_title
            )

    except Exception as e:
        logger.error(f"Xabar skanerlash xatosi: {e}", exc_info=True)