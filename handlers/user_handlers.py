# handlers/user_handlers.py
import asyncio
import logging
import os
from typing import Optional
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ErrorEvent
from aiogram.fsm.context import FSMContext

from analyzers import analyze_text, scan_url, scan_file
from db import db
from config import config
from keyboards.main_keyboard import get_main_keyboard
from utils.helpers import cleanup_temp_file

logger = logging.getLogger(__name__)
router = Router(name="user_handlers")

# --- Xatolarni tutuvchi handler (Global Error Handler) ---
@router.error()
async def error_handler(event: ErrorEvent):
    """Barcha kutilmagan xatolarni tutib oladi."""
    logger.error(f"Kutilmagan xatolik: {event.exception}", exc_info=True)
    # Agar xabar yuborish imkoni bo'lsa
    if event.update.message:
        await event.update.message.answer("⚠️ Tizimda texnik xatolik yuz berdi. Birozdan so'ng urinib ko'ring.")

@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    await db.add_user(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name
    )

    text = (
        f"Assalomu alaykum, {user.full_name or user.first_name}! 👋\n\n"
        "Men <b>Kiber-Inspektor</b> – xavfli havola va fayllarni aniqlayman.\n\n"
        "Buyruqlar:\n"
        "• Matnni tekshirish: /check [matn]\n"
        "• Havolani skanerlash: /scanurl [url]\n"
        "• Fayl yuboring – avto-skan\n\n"
        "Xavfsiz bo'ling! 🔒"
    )
    keyboard = get_main_keyboard(is_admin=user.id in config.ADMIN_IDS)
    await message.answer(text, reply_markup=keyboard, disable_web_page_preview=True)

@router.message(Command("check"))
async def cmd_check(message: Message):
    text = message.text.strip().replace("/check", "", 1).strip()
    if not text:
        await message.reply("Tekshirish uchun matn yuboring.")
        return

    result = analyze_text(text, config.AI_THRESHOLD)
    emoji = "🟢" if result["threat"] == "Safe" else "🟡" if result["threat"] == "Low" else "🔴"
    
    reply_text = (
        f"{emoji} <b>Tahlil natijasi:</b>\n"
        f"• Xavf darajasi: <b>{result['threat']}</b>\n"
        f"• Score: <b>{result['score']:.2%}</b>\n"
        f"• Sabab: {result['reason']}"
    )
    await message.reply(reply_text)
    await db.log_message(None, message.from_user.id, text, result["threat"])

@router.message(Command("scanurl"))
async def cmd_scanurl(message: Message):
    args = message.text.strip().split(maxsplit=1)
    if len(args) < 2:
        await message.reply("URL yuboring. Masalan: /scanurl google.com")
        return

    url = args[1].strip()
    if not url.startswith(('http://', 'https://')):
        url = "https://" + url

    status_msg = await message.reply("🔍 URL tekshirilmoqda...")
    result = await scan_url(url)

    emoji = "🟢" if result["threat"] == "Safe" else "🟡" if result["threat"] == "Low" else "🔴"
    reply_text = (
        f"{emoji} <b>URL tahlili:</b>\n"
        f"• Xavf: <b>{result['threat']}</b>\n"
        f"• VirusTotal: {result['malicious']}/{result['suspicious']}\n"
        f"• Sabab: {result['reason']}"
    )
    await status_msg.edit_text(reply_text, disable_web_page_preview=True)

# --- Tuzatilgan Fayl Handler ---
@router.message(F.document | F.photo | F.video | F.audio | F.voice)
async def handle_file(message: Message):
    """Har qanday fayl yuborilganda xavfsiz skanerlash."""
    temp_path = None  # UnboundLocalError ning oldini olish uchun
    
    # Media turini aniqlash
    if message.document:
        media = message.document
        file_name = media.file_name or f"file_{media.file_id[:8]}"
    elif message.photo:
        media = message.photo[-1]  # Eng sifatli rasm
        file_name = f"photo_{media.file_id[:8]}.jpg"
    elif message.video:
        media = message.video
        file_name = media.file_name or f"video_{media.file_id[:8]}.mp4"
    elif message.audio:
        media = message.audio
        file_name = media.file_name or f"audio_{media.file_id[:8]}.mp3"
    elif message.voice:
        media = message.voice
        file_name = f"voice_{media.file_id[:8]}.ogg"
    else:
        return

    # Hajmni tekshirish
    if media.file_size > config.MAX_FILE_SIZE:
        await message.reply(f"❌ Fayl juda katta! Max: {config.MAX_FILE_SIZE // 1048576} MB")
        return

    status_msg = await message.reply("📁 Fayl tahlil qilinmoqda...")

    try:
        # Faylni yuklab olish
        file_info = await message.bot.get_file(media.file_id)
        os.makedirs(config.TEMP_DIR, exist_ok=True)
        temp_path = os.path.join(config.TEMP_DIR, f"{media.file_id}_{file_name}")

        await message.bot.download_file(file_info.file_path, destination=temp_path)

        # Skanerlash
        result = await scan_file(temp_path)

        emoji = "🟢" if result["threat"] == "Safe" else "🟡" if result["threat"] == "Low" else "🔴"
        reply_text = (
            f"{emoji} <b>Fayl tahlili:</b>\n"
            f"• Xavf darajasi: <b>{result['threat']}</b>\n"
            f"• VirusTotal: {result['positives']} / {result['total']}\n"
            f"• Sabab: {result['reason']}"
        )
        await status_msg.edit_text(reply_text)

        # Loglash
        await db.log_message(
            group_id=message.chat.id if message.chat.type != "private" else None,
            user_id=message.from_user.id,
            text=f"Fayl: {file_name}",
            threat_level=result["threat"]
        )

    except Exception as e:
        logger.error(f"Fayl skan xatosi: {e}", exc_info=True)
        await status_msg.edit_text("❌ Tekshirishda xatolik yuz berdi.")
    
    finally:
        if temp_path:
            cleanup_temp_file(temp_path)

@router.message()
async def echo_handler(message: Message):
    if message.chat.type in ("group", "supergroup"):
        return
    if message.text and len(message.text) > 20:
        await cmd_check(message)