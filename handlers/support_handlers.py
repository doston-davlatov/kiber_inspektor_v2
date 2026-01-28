# handlers/support_handlers.py
"""
Support tizimi: foydalanuvchi so'rovlarini yuborish, admin javob berish.
Komandalar: /support <subject> <message>, /requests (admin uchun), /reply <request_id> <message>
"""

import logging
from typing import Optional
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

from db import db
from config import config
from keyboards.main_keyboard import get_support_keyboard  # keyingi qadamda yoziladi
from utils.helpers import is_admin

logger = logging.getLogger(__name__)

router = Router(name="support_handlers")

# FSM states support uchun
class SupportForm(StatesGroup):
    subject = State()
    message = State()
    request_id = State()  # Admin javob berish uchun

@router.message(Command("support"))
async def cmd_support(message: Message, state: FSMContext):
    """Support so'rov yuborish: /support <subject> <message> yoki FSM orqali."""
    args = message.text.strip().replace("/support", "", 1).strip()
    if not args:
        await message.reply("Mavzu kiriting:")
        await state.set_state(SupportForm.subject)
        return

    # Agar to'liq bo'lsa
    parts = args.split(maxsplit=1)
    subject = parts[0]
    msg_text = parts[1] if len(parts) > 1 else ""

    if not msg_text:
        await state.update_data(subject=subject)
        await message.reply("Xabar matnini kiriting:")
        await state.set_state(SupportForm.message)
        return

    request_id = await db.create_support_request(
        user_id=message.from_user.id,
        subject=subject,
        message=msg_text
    )
    if request_id:
        await message.reply(f"✅ So'rovingiz qabul qilindi! ID: {request_id}")
        # Adminlarga xabar yuborish
        for admin_id in config.ADMIN_IDS:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"Yangi support so'rovi: ID {request_id} foydalanuvchidan {message.from_user.username}"
                )
            except TelegramBadRequest:
                pass
    else:
        await message.reply("❌ So'rovni saqlashda xato.")

    await state.clear()


@router.message(SupportForm.subject)
async def process_subject(message: Message, state: FSMContext):
    await state.update_data(subject=message.text.strip())
    await message.reply("Xabar matnini kiriting:")
    await state.set_state(SupportForm.message)


@router.message(SupportForm.message)
async def process_message(message: Message, state: FSMContext):
    data = await state.get_data()
    subject = data.get("subject")
    msg_text = message.text.strip()

    request_id = await db.create_support_request(
        user_id=message.from_user.id,
        subject=subject,
        message=msg_text
    )
    if request_id:
        await message.reply(f"✅ So'rovingiz qabul qilindi! ID: {request_id}")
        # Adminlarga alert
        for admin_id in config.ADMIN_IDS:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"Yangi support: ID {request_id} - {subject}"
                )
            except:
                pass
    else:
        await message.reply("❌ Xato yuz berdi.")

    await state.clear()


@router.message(Command("requests"))
async def cmd_requests(message: Message):
    """Admin uchun: barcha support so'rovlarini ko'rsatish."""
    if not is_admin(message.from_user.id):
        await message.reply("❌ Faqat adminlar uchun!")
        return

    requests = await db.get_support_requests(status="pending")
    if not requests:
        await message.reply("Hech qanday yangi so'rov yo'q.")
        return

    text = "<b>Yangi support so'rovlari:</b>\n\n"
    for req in requests:
        text += (
            f"• ID: {req['id']}\n"
            f"   Foydalanuvchi: @{req['username']} ({req['user_id']})\n"
            f"   Mavzu: {req['subject']}\n"
            f"   Oxirgi xabar: {req['last_message'][:50]}...\n"
            f"   Vaqt: {req['created_at']}\n\n"
        )

    keyboard = get_support_keyboard(requests)  # Inline tugmalar requestlarga

    await message.reply(text, reply_markup=keyboard)


@router.message(Command("reply"))
async def cmd_reply(message: Message, state: FSMContext):
    """Admin uchun: /reply <request_id> <message>."""
    if not is_admin(message.from_user.id):
        await message.reply("❌ Faqat adminlar uchun!")
        return

    args = message.text.strip().split(maxsplit=2)
    if len(args) < 3:
        await message.reply("Foydalanish: /reply <request_id> <xabar>")
        return

    try:
        request_id = int(args[1])
        msg_text = args[2]

        req = await db.get_support_request(request_id)
        if not req:
            await message.reply(f"❌ So'rov {request_id} topilmadi.")
            return

        added = await db.add_support_message(
            request_id=request_id,
            sender_id=message.from_user.id,
            message=msg_text,
            is_from_user=False
        )
        if added:
            await db.update_support_request(request_id, status="in_progress")
            await message.reply(f"✅ Javob yuborildi: {request_id}")

            # Foydalanuvchiga yuborish
            try:
                await message.bot.send_message(
                    req["user_id"],
                    f"Admin javobi (ID {request_id}): {msg_text}"
                )
            except TelegramBadRequest:
                await message.reply("⚠️ Foydalanuvchiga yuborib bo'lmadi (botni bloklagan bo'lishi mumkin).")
        else:
            await message.reply("❌ Javobni saqlashda xato.")
    except ValueError:
        await message.reply("❌ Request ID raqam bo'lishi kerak.")


@router.callback_query(F.data.startswith("support_"))
async def support_callback(query: CallbackQuery, state: FSMContext):
    """Inline tugmalar orqali supportlarni boshqarish."""
    if not is_admin(query.from_user.id):
        await query.answer("❌ Faqat adminlar uchun!", show_alert=True)
        return

    data = query.data.split("_")[1:]
    action = data[0]
    request_id = int(data[1])

    if action == "view":
        conversation = await db.get_support_conversation(request_id)
        text = "<b>Support suhbati:</b>\n\n"
        for msg in conversation:
            sender = "Foydalanuvchi" if msg["is_from_user"] else "Admin"
            text += f"{sender} ({msg['created_at']}): {msg['message_text']}\n\n"

        await query.message.edit_text(text)
        await query.answer("Suhbat ko'rsatildi.")

    elif action == "close":
        updated = await db.update_support_request(request_id, status="closed")
        if updated:
            await query.message.edit_text("✅ So'rov yopildi.")
            await query.answer("Yopildi!")
        else:
            await query.answer("❌ Xato yuz berdi.", show_alert=True)

    elif action == "reply":
        await state.update_data(request_id=request_id)
        await query.message.reply("Javob matnini yozing:")
        await state.set_state(SupportForm.message)  # FSM orqali javob

# FSM orqali admin javobini qabul qilish
@router.message(SupportForm.message)
async def process_admin_reply(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    request_id = data.get("request_id")
    if not request_id:
        await message.reply("❌ Request ID topilmadi.")
        await state.clear()
        return

    msg_text = message.text.strip()
    added = await db.add_support_message(
        request_id=request_id,
        sender_id=message.from_user.id,
        message=msg_text,
        is_from_user=False
    )
    if added:
        await db.update_support_request(request_id, status="in_progress", message=msg_text)
        await message.reply(f"✅ Javob yuborildi: {request_id}")

        req = await db.get_support_request(request_id)
        try:
            await message.bot.send_message(req["user_id"], f"Admin javobi: {msg_text}")
        except:
            pass
    else:
        await message.reply("❌ Xato.")

    await state.clear()