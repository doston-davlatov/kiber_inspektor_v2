# handlers/admin_handlers.py
import logging
import asyncio
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db import db
from config import config
from keyboards.main_keyboard import get_admin_keyboard 
from utils.helpers import format_stats_message

logger = logging.getLogger(__name__)
router = Router(name="admin_handlers")

# Reklama/Xabar yuborish uchun holatlar
class BroadcastStates(StatesGroup):
    waiting_for_message = State()

# --- Admin Middleware (Faqat adminlar kira olishi uchun) ---
@router.message(lambda m: m.from_user.id not in config.ADMIN_IDS)
async def non_admin_blocker(message: Message):
    admin_commands = ('/stats', '/ban', '/unban', '/user', '/broadcast', '/recent_threats')
    if message.text and message.text.startswith(admin_commands):
        await message.reply("❌ Siz admin emassiz! Bu buyruqlar faqat ruxsat etilgan adminlar uchun.")
        return

# --- Statistika ---
@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Bot statistikasini ko'rsatish."""
    stats = await db.get_stats()
    daily_stats = await db.get_daily_stats(days=7)
    recent_threats = await db.get_recent_threats(limit=5)

    text = format_stats_message(stats, daily_stats, recent_threats)
    keyboard = get_admin_keyboard()
    await message.reply(text, reply_markup=keyboard)

# --- Ban / Unban ---
@router.message(Command("ban"))
async def cmd_ban(message: Message):
    args = message.text.strip().split()
    if len(args) < 2:
        await message.reply("Foydalanish: /ban <user_id>")
        return

    try:
        user_id = int(args[1])
        banned = await db.ban_user(user_id)
        if banned:
            await message.reply(f"✅ Foydalanuvchi {user_id} ban qilindi.")
            try:
                await message.bot.send_message(user_id, "❌ Siz botdan foydalanish huquqidan mahrum qilindingiz (BAN)!")
            except Exception:
                pass
        else:
            await message.reply(f"❌ {user_id} topilmadi yoki allaqachon banlangan.")
    except ValueError:
        await message.reply("❌ User ID raqam bo'lishi kerak.")

@router.message(Command("unban"))
async def cmd_unban(message: Message):
    args = message.text.strip().split()
    if len(args) < 2:
        await message.reply("Foydalanish: /unban <user_id>")
        return

    try:
        user_id = int(args[1])
        unbanned = await db.unban_user(user_id)
        if unbanned:
            await message.reply(f"✅ Foydalanuvchi {user_id} bandan chiqarildi.")
            try:
                await message.bot.send_message(user_id, "✅ Sizning baningiz ochildi! Botdan foydalanishingiz mumkin.")
            except Exception:
                pass
        else:
            await message.reply(f"❌ {user_id} topilmadi yoki banlanmagan.")
    except ValueError:
        await message.reply("❌ User ID raqam bo'lishi kerak.")

# --- Foydalanuvchi ma'lumoti ---
@router.message(Command("user"))
async def cmd_user_info(message: Message):
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
            f"👤 <b>Foydalanuvchi ma'lumotlari:</b>\n"
            f"• ID: <code>{user_stats['user_id']}</code>\n"
            f"• Username: @{user_stats['username'] or 'yo\'q'}\n"
            f"• Ism: {user_stats['full_name']}\n"
            f"• Ro'yxatdan o'tdi: {user_stats['created_at']}\n"
            f"• Jami xabarlar: {user_stats['total_messages']}\n"
            f"• Xavfli xabarlar: {user_stats['threat_messages']}\n"
            f"• Status: {'🔴 BAN' if user_stats.get('is_banned') else '🟢 Faol'}"
        )
        await message.reply(text)
    except ValueError:
        await message.reply("❌ User ID raqam bo'lishi kerak.")

# --- HAMMAGA XABAR YUBORISH (BROADCAST) ---
@router.message(Command("broadcast"))
async def start_broadcast(message: Message, state: FSMContext):
    """Barcha foydalanuvchilarga xabar yuborishni boshlash."""
    await message.reply("📢 Barcha foydalanuvchilarga yuboriladigan xabarni (rasm, matn, video) kiriting.\n\nBekor qilish uchun /cancel deb yozing.")
    await state.set_state(BroadcastStates.waiting_for_message)

@router.message(BroadcastStates.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    if message.text == "/cancel":
        await state.clear()
        await message.reply("❌ Xabar yuborish bekor qilindi.")
        return

    all_users = await db.get_all_users() # Bazadan barcha userlarni olish
    if not all_users:
        await message.reply("Bazada foydalanuvchilar yo'q.")
        await state.clear()
        return

    count = 0
    blocked_count = 0
    status_msg = await message.reply(f"🚀 Xabar yuborish boshlandi (Jami: {len(all_users)} ta)...")

    for user in all_users:
        try:
            await bot.copy_message(
                chat_id=user['user_id'],
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            count += 1
            # Telegram limitlariga tushib qolmaslik uchun
            if count % 20 == 0:
                await asyncio.sleep(0.1)
        except TelegramForbiddenError:
            blocked_count += 1
        except Exception as e:
            logger.error(f"Xabar yuborishda xato ({user['user_id']}): {e}")

    await state.clear()
    await status_msg.edit_text(
        f"✅ <b>Xabar yuborish tugallandi!</b>\n\n"
        f"• Muvaffaqiyatli: {count}\n"
        f"• Botni bloklaganlar: {blocked_count}\n"
        f"• Jami: {len(all_users)}"
    )

# --- Inline tugmalar uchun callback ---
@router.callback_query(F.data.startswith("admin_"))
async def admin_callback(query: CallbackQuery, state: FSMContext):
    action = query.data.split("_")[1]
    
    if action == "stats":
        await cmd_stats(query.message)
    elif action == "broadcast":
        await start_broadcast(query.message, state)
    
    await query.answer()