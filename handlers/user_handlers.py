# handlers/user_handlers.py
"""
Foydalanuvchi komandalari va oddiy xabarlar uchun handlerlar:
- /start
- /check <matn>
- /scanurl <url>
- Fayl yuborilganda avtomatik skan
- Oddiy matn xabarlari (guruhlarda monitoring)
"""

import asyncio
import logging
import os
from typing import Optional
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, FSInputFile, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from analyzers import analyze_text, scan_url, scan_file
from db import db
from config import config
from keyboards.main_keyboard import get_main_keyboard  # keyingi qadamda yoziladi
from utils.helpers import cleanup_temp_file

logger = logging.getLogger(__name__)

router = Router(name="user_handlers")

@router.message(CommandStart())
async def cmd_start(message: Message):
    """/start komandasi – botni boshlash va foydalanuvchini ro'yxatdan o'tkazish."""
    user = message.from_user
    added = await db.add_user(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name
    )

    text = (
        f"Assalomu alaykum, {user.full_name or user.first_name}! 👋\n\n"
        "Men <b>Kiber-Inspektor</b> – Telegramdagi xavfli havolalar, fayllar va scam xabarlarni aniqlayman.\n\n"
        "Nima qila olaman:\n"
        "• Matnni tekshirish: /check [matn]\n"
        "• Havolani skanerlash: /scanurl [url]\n"
        "• Fayl yuboring – avto-skan qilaman\n"
        "• Guruhda ishlayman – xavfli xabarlarni ogohlantiraman\n\n"
        "Xavfsiz bo'ling! 🔒"
    )

    keyboard = get_main_keyboard(is_admin=user.id in config.ADMIN_IDS)

    await message.answer(text, reply_markup=keyboard, disable_web_page_preview=True)


@router.message(Command("check"))
async def cmd_check(message: Message):
    """Matnni scam/phishing uchun tekshirish."""
    await db.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)

    text = message.text.strip().replace("/check", "", 1).strip()
    if not text:
        await message.reply("Tekshirish uchun matn yuboring.\nMasalan: /check Siz 5 million yutdingiz!")
        return

    result = analyze_text(text, config.AI_THRESHOLD)

    emoji = "🟢" if result["threat"] == "Safe" else "🟡" if result["threat"] == "Low" else "🔴"
    reply_text = (
        f"{emoji} <b>Tahlil natijasi:</b>\n"
        f"• Xavf darajasi: <b>{result['threat']}</b>\n"
        f"• Ishonchsizlik darajasi: <b>{result['score']:.2%}</b>\n"
        f"• Sabab: {result['reason']}\n\n"
        f"Asl matn: {text[:200]}{'...' if len(text) > 200 else ''}"
    )

    await message.reply(reply_text, disable_web_page_preview=True)

    # Loglash
    await db.log_message(
        group_id=None,
        user_id=message.from_user.id,
        text=text,
        threat_level=result["threat"]
    )


@router.message(Command("scanurl"))
async def cmd_scanurl(message: Message):
    """URL ni skanerlash."""
    await db.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)

    args = message.text.strip().split(maxsplit=1)
    if len(args) < 2:
        await message.reply("URL yuboring.\nMasalan: /scanurl https://example.com")
        return

    url = args[1].strip()
    if not url.startswith(('http://', 'https://')):
        url = "https://" + url

    await message.reply("🔍 URL tekshirilmoqda... (VirusTotal + qo'shimcha tekshiruvlar)")

    result = await scan_url(url)

    emoji = "🟢" if result["threat"] == "Safe" else "🟡" if result["threat"] == "Low" else "🔴"
    reply_text = (
        f"{emoji} <b>URL tahlili:</b>\n"
        f"• Xavf darajasi: <b>{result['threat']}</b>\n"
        f"• VirusTotal: {result['malicious']} malicious / {result['suspicious']} suspicious\n"
        f"• SSL sertifikat: {'✅ to\'g\'ri' if result['ssl_valid'] else '⚠️ muammo'}\n"
        f"• Redirectlar: {'bor' if result['redirects'] else 'yo\'q'}\n"
        f"• Sabab: {result['reason']}\n\n"
        f"Havola: {url}"
    )

    await message.reply(reply_text, disable_web_page_preview=True)


@router.message(F.document | F.photo | F.video | F.audio | F.voice)
async def handle_file(message: Message):
    """Har qanday fayl yuborilganda skanerlash."""
    await db.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)

    document = message.document or message.photo[-1] if message.photo else \
               message.video or message.audio or message.voice

    if not document:
        return

    file_size = document.file_size
    if file_size > config.MAX_FILE_SIZE:
        await message.reply(f"❌ Fayl juda katta! Maksimal: {config.MAX_FILE_SIZE // 1024 // 1024} MB")
        return

    await message.reply("📁 Fayl yuklab olinmoqda va tekshirilmoqda...")

    try:
        file_info = await message.bot.get_file(document.file_id)
        downloaded_file = await message.bot.download_file(file_info.file_path)

        temp_path = os.path.join(config.TEMP_DIR, f"{document.file_id}_{document.file_name or 'file'}")
        os.makedirs(config.TEMP_DIR, exist_ok=True)

        with open(temp_path, "wb") as f:
            f.write(downloaded_file.read())

        result = await scan_file(temp_path)

        emoji = "🟢" if result["threat"] == "Safe" else "🟡" if result["threat"] == "Low" else "🔴"
        reply_text = (
            f"{emoji} <b>Fayl tahlili:</b>\n"
            f"• Xavf darajasi: <b>{result['threat']}</b>\n"
            f"• VirusTotal: {result['positives']} / {result['total']} engine xavfli deb topdi\n"
            f"• Hash (SHA256): <code>{result['sha256'][:16]}...</code>\n"
            f"• Sabab: {result['reason']}"
        )

        await message.reply(reply_text)

        # Loglash
        await db.log_message(
            group_id=message.chat.id if message.chat.type in ("group", "supergroup") else None,
            user_id=message.from_user.id,
            text=f"Fayl skan qilindi: {document.file_name or 'noma\'lum'}",
            threat_level=result["threat"]
        )

    except Exception as e:
        logger.error(f"Fayl skan xatosi: {e}", exc_info=True)
        await message.reply("❌ Faylni tekshirishda xato yuz berdi. Qayta urinib ko'ring.")
    finally:
        cleanup_temp_file(temp_path)


@router.message()
async def echo_handler(message: Message):
    """Oddiy matn xabarlari – agar guruhda bo'lsa, avto-tekshirish."""
    if message.chat.type in ("group", "supergroup"):
        # Guruh monitoringi uchun group_handlers.py da alohida handler bor
        return

    # Shaxsiy chatda oddiy matn bo'lsa – /check ga o'xshash ishlatish mumkin
    if message.text and len(message.text) > 20:
        await cmd_check(message)


# Qo'shimcha: Fayl hajmini cheklash va temp fayllarni tozalash
def cleanup_temp_file(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except:
        pass