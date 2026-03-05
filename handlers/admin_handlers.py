# handlers/admin_handlers.py
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.markdown import hbold

from db import db
from config import config

logger = logging.getLogger(__name__)
router = Router(name="admin_handlers")

@router.message(Command("threats"))
async def cmd_threats(message: Message):
    if message.from_user.id not in config.ADMIN_IDS:
        await message.reply("Bu buyruq faqat adminlar uchun.")
        return

    threats = await db.get_threats(limit=20)

    if not threats:
        await message.reply("Hozircha aniqlangan xavf yo'q.")
        return

    lines = ["🔴 Aniqlangan xavflar (oxirgi 20 ta)\n"]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    for t in threats:
        chat_type = t["chat_type"].upper()
        title = t["chat_title"] or "Noma'lum"
        user = t["user_id"]
        level = hbold(t["threat_level"])
        text_preview = (t["message_text"][:90] + "...") if len(t["message_text"]) > 90 else t["message_text"]
        reason = t["threat_reason"] or "—"
        time_str = t["created_at"].strftime("%Y-%m-%d %H:%M")

        line = (
            f"• {level} | {chat_type} ({title})\n"
            f"  👤 {user}\n"
            f"  📝 {text_preview}\n"
            f"  💡 {reason}\n"
            f"  🕒 {time_str}\n"
        )
        lines.append(line)

        if t["chat_type"] in ("group", "supergroup", "channel") and t["message_id"]:
            chat_id_str = str(abs(t["chat_id"]))
            if chat_id_str.startswith("100"):
                chat_id_str = chat_id_str[3:]
            link = f"https://t.me/c/{chat_id_str}/{t['message_id']}"
            btn = InlineKeyboardButton("↗️ Xabarga o'tish", url=link)
            keyboard.inline_keyboard.append([btn])

        lines.append("─" * 40)

    text = "".join(lines).rstrip()

    if keyboard.inline_keyboard:
        await message.reply(text, reply_markup=keyboard)
    else:
        await message.reply(text)

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id not in config.ADMIN_IDS:
        return
    await message.reply("Statistika hali to'liq amalga oshirilmagan.\n/threats — xavflar ro'yxati")