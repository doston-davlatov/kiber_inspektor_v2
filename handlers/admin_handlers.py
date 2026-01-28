# handlers/admin_handlers.py
"""
Admin komandalari: statistika, ban/unban, foydalanuvchi info va boshqalar.
Admin bo'lish uchun user ID config.ADMIN_IDS da bo'lishi kerak.
"""

import logging
from typing import Optional
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from db import db
from config import config
from keyboards.main_keyboard import get_admin_keyboard  # keyingi qadamda yoziladi
from utils.helpers import format_stats_message, is_admin  # utils/helpers.py da yoziladi (keyingi qadam)

logger = logging.getLogger(__name__)

router = Router(name="admin_handlers")

# Admin middleware (faqat adminlar uchun)
@router.message(F.from_user.id.not_in(config.ADMIN_IDS))
async def non_admin_blocker(message: Message):
    if message.text and message.text.startswith(('/stats', '/ban', '/unban', '/user')):
        await message.reply("❌ Siz admin emassiz! Admin bilan bog'laning.")
        return

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Bot statistikasini ko'rsatish: users, groups, threats."""
    stats = await db.get_stats()
    daily_stats = await db.get_daily_stats(days=7)
    recent_threats = await db.get_recent_threats(limit=5)

    text = format_stats_message(stats, daily_stats, recent_threats)
    keyboard = get_admin_keyboard()

    await message.reply(text, reply_markup=keyboard)


@router.message(Command("ban"))
async def cmd_ban(message: Message):
    """Foydalanuvchini ban qilish: /ban <user_id>."""
    args = message.text.strip().split()
    if len(args) < 2:
        await message.reply("Foydalanish: /ban <user_id>")
        return

    try:
        user_id = int(args[1])
        banned = await db.ban_user(user_id)
        if banned:
            await message.reply(f"✅ Foydalanuvchi {user_id} ban qilindi.")
            # Ban haqida foydalanuvchiga xabar yuborish (agar kerak bo'lsa)
            try:
                await message.bot.send_message(user_id, "❌ Siz botdan ban qilindingiz!")
            except TelegramBadRequest:
                pass
        else:
            await message.reply(f"❌ {user_id} topilmadi yoki allaqachon ban.")
    except ValueError:
        await message.reply("❌ User ID raqam bo'lishi kerak.")


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    """Ban ni ochish: /unban <user_id>."""
    args = message.text.strip().split()
    if len(args) < 2:
        await message.reply("Foydalanish: /unban <user_id>")
        return

    try:
        user_id = int(args[1])
        unbanned = await db.unban_user(user_id)
        if unbanned:
            await message.reply(f"✅ Foydalanuvchi {user_id} ban ochildi.")
            try:
                await message.bot.send_message(user_id, "✅ Siz botdan ban ochildi!")
            except TelegramBadRequest:
                pass
        else:
            await message.reply(f"❌ {user_id} topilmadi yoki ban emas.")
    except ValueError:
        await message.reply("❌ User ID raqam bo'lishi kerak.")


@router.message(Command("user"))
async def cmd_user_info(message: Message):
    """Foydalanuvchi haqida info: /user <user_id>."""
    args = message.text.strip().split()
    if len(args) < 2:
        await message.reply("Foydalanish: /user <user_id>")
        return

    try:
        user_id = int(args[1])
        user_stats = await db.get_user_stats(user_id)
        if not user_stats:
            await message.reply(f"❌ {user_id} topilmadi.")
            return

        text = (
            f"<b>Foydalanuvchi info:</b>\n"
            f"• ID: {user_stats['user_id']}\n"
            f"• Username: @{user_stats['username'] or 'yo\'q'}\n"
            f"• Ism: {user_stats['full_name']}\n"
            f"• Ishonch darajasi: {user_stats['trust_score']}\n"
            f"• Ro'yxatdan o'tgan: {user_stats['created_at']}\n"
            f"• Jami xabarlar: {user_stats['total_messages']}\n"
            f"• Xavfli xabarlar: {user_stats['threat_messages']}\n"
            f"• Oxirgi faollik: {user_stats['last_activity'] or 'yo\'q'}"
        )
        await message.reply(text)
    except ValueError:
        await message.reply("❌ User ID raqam bo'lishi kerak.")


@router.message(Command("recent_threats"))
async def cmd_recent_threats(message: Message):
    """Oxirgi xavfli xabarlar: /recent_threats [limit=10]."""
    args = message.text.strip().split()
    limit = 10
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass

    threats = await db.get_recent_threats(limit=limit)
    if not threats:
        await message.reply("Hech qanday xavfli xabar topilmadi.")
        return

    text = "<b>Oxirgi xavfli xabarlar:</b>\n\n"
    for threat in threats:
        text += (
            f"• ID: {threat['id']}\n"
            f"   User: @{threat['username']} ({threat['user_id']})\n"
            f"   Guruh: {threat['group_name'] or 'Shaxsiy'} ({threat['group_id'] or ''})\n"
            f"   Daraja: {threat['threat_level']}\n"
            f"   Vaqt: {threat['created_at']}\n"
            f"   Matn: {threat['message_text'][:100]}...\n\n"
        )

    await message.reply(text)


# Callback query handler (masalan, inline tugmalar uchun)
@router.callback_query(F.data.startswith("admin_"))
async def admin_callback(query: CallbackQuery):
    data = query.data.split("_")[1:]
    if data[0] == "stats":
        # Masalan, yangi stats olish
        await cmd_stats(query.message)
    await query.answer("Amal bajarildi!")


# Admin bo'lishini tekshiruvchi helper (utils ga ko'chirilishi mumkin)
def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS