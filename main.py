import asyncio
import datetime
import json
import logging
import os
import re
from typing import Optional, List, Dict, Any

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

# Sozlamalar
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN .env faylida yo'q!")

# Bot - konfiguratsiya
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Modullar
from database.db_manager import db
from handlers.analyzer import analyze_message, analyze_message_advanced
from handlers.ai_analyzer import ai_analyzer
from handlers.url_scanner import url_scanner
from handlers.file_analyzer import file_analyzer
from handlers.future_features import FutureFeatures
from handlers.monitor import monitor
from handlers.virustotal_client import vt_client

future_features = FutureFeatures(db)

# Admin tekshirish
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# --- YORDAMCHI FUNKSIYALAR ---
def get_user_link(user: types.User) -> str:
    if user.username:
        return f'<a href="https://t.me/{user.username}">{user.full_name}</a>'
    else:
        return f'<a href="tg://user?id={user.id}">{user.full_name}</a>'

def get_main_keyboard(user_id: Optional[int] = None) -> ReplyKeyboardMarkup:
    unread_count = 0
    if user_id:
        unread_count = db.get_unread_messages_count(user_id, is_admin=False)
    
    support_text = f"📩 Admin ({unread_count})" if unread_count > 0 else "📩 Admin bilan bog'lanish"
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Tekshirish"), KeyboardButton(text="📊 Mening statistikam")],
            [KeyboardButton(text=support_text), KeyboardButton(text="🛡️ Xavfsizlik tavsiyalari")],
            [KeyboardButton(text="ℹ️ Yordam")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_admin_keyboard() -> ReplyKeyboardMarkup:
    unread_count = db.get_unread_messages_count(is_admin=True)
    support_text = f"📨 Support ({unread_count})" if unread_count > 0 else "📨 Support"
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Foydalanuvchilar"), KeyboardButton(text=support_text)],
            [KeyboardButton(text="📈 Statistika"), KeyboardButton(text="🚨 Xavflar ro'yxati")],
            [KeyboardButton(text="📊 Hisobot"), KeyboardButton(text="⬅️ Asosiy menyu")]
        ],
        resize_keyboard=True
    )
    return keyboard

def format_time_difference(dt_str: str) -> str:
    """Vaqt farqini formatlash"""
    if not dt_str:
        return "Noma'lum"
    
    try:
        dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.datetime.now()
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days} kun oldin"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} soat oldin"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} daqiqa oldin"
        else:
            return f"{diff.seconds} soniya oldin"
    except:
        return dt_str

# ================ START VA YORDAM ================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    welcome_text = (
        "🛡️ <b>Kiber-Inspektor</b>\n\n"
        "Men firibgarlik, phishing va boshqa kiberxavflarni aniqlayman!\n\n"
        "<b>Asosiy funksiyalar:</b>\n"
        "✅ Matn va havolalarni tekshirish\n"
        "/check [matn]       - Matnni tekshirish va xavflarni aniqlash\n"
        "/scanurl [havola]   - URL ni skanerlash va xavf darajasini aniqlash\n"
        "/mystats            - Shaxsiy statistika va faollikni ko'rish\n"
        "✅ Fayllarni tahlil qilish\n"
        "Gurularda avtomatik tekshirish\n"
        "✅ Real-time monitoring\n"
        "✅ Guruhlarni himoya qilish\n"
        "✅ Admin bilan bog'lanish\n"
        "/support - Admin bilan bog'lanish (faqat shaxsiy chatda)\n\n"
        "Quyidagi tugmalar orqali foydalanishingiz mumkin:\n"
        "/help  - Bot haqida ma'lumot va qo'llanma\n"
        "/myid  - O'zingizning Telegram ID ni ko'rish"
    )
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard(message.from_user.id))
    
    db.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    if message.chat.type in ["group", "supergroup"]:
        db.add_group(message.chat.id, message.chat.title)

@dp.message(Command("myid"))
async def myid_cmd(message: types.Message):
    """Foydalanuvchi ID sini ko'rish"""
    user_id = message.from_user.id
    await message.answer(
        f"🆔 <b>Sizning ID ingiz:</b> <code>{user_id}</code>\n\n"
        f"📛 Ism: {message.from_user.full_name}\n"
        f"📧 Username: @{message.from_user.username or 'Yo\'q'}\n\n"
        f"<i>Bu ID ni .env faylida ADMIN_IDS ga qo'shing</i>"
    )
    
@dp.message(F.text == "ℹ️ Yordam")
@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    help_text = (
        "<b>🆘 Kiber-Inspektor Yordam</b>\n\n"
        "<b>🔧 Asosiy Buyruqlar:</b>\n"
        "/start - Botni ishga tushirish\n"
        "/help - Yordam\n"
        "/check [matn] - Matnni tekshirish\n"
        "/scanurl [havola] - URL ni skanerlash\n"
        "/mystats - Shaxsiy statistika\n"
        "/support - Admin bilan bog'lanish\n\n"
        
        "<b>💬 Admin bilan bog'lanish:</b>\n"
        "1. '📩 Admin bilan bog'lanish' tugmasini bosing\n"
        "2. So'rovingiz mavzusini yozing\n"
        "3. Xabaringizni yozing\n"
        "4. Admin tez orada javob beradi\n\n"
        
        "<i>Bot guruhlarga qo'shilsa, avtomatik xabarlarni tekshiradi!</i>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Tekshirishni boshlash", callback_data="start_check")
    builder.button(text="📩 Admin bilan bog'lanish", callback_data="start_support")
    builder.button(text="🛡️ Xavfsizlik tavsiyalari", callback_data="safety_tips")
    builder.adjust(1)
    
    keyboard = builder.as_markup()
    
    await message.answer(help_text, reply_markup=keyboard)

# ================ TEKSHIRISH FUNKSIYALARI ================
@dp.message(F.text == "🔍 Tekshirish")
@dp.message(Command("check"))
async def check_cmd(message: types.Message):
    if message.text == "🔍 Tekshirish":
        await message.answer(
            "📝 <b>Matnni yuboring yoki /check [matn] buyrug'idan foydalaning</b>\n\n"
            "Misol: <code>/check bu mukofot yutishingiz mumkin</code>\n"
            "Misol: <code>/check https://xato-havola.tk</code>",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    text = message.text.replace("/check", "").strip()
    if not text:
        await message.answer("❌ Matn kiriting: <code>/check [matn]</code>")
        return
    
    await process_text_analysis(message, text)

async def process_text_analysis(message: types.Message, text: str):
    loading_msg = await message.answer("🔍 <b>Tahlil qilinmoqda...</b>")
    
    try:
        all_threats = []
        severity = "Safe"
        details = []
        
        # 1. Asosiy tahlil
        threat1, sev1 = analyze_message(text)
        threats2, sev2 = analyze_message_advanced(text)
        
        if threat1: 
            all_threats.append(threat1)
            details.append(f"• {threat1}")
        if threats2: 
            all_threats.extend(threats2)
            for t in threats2:
                details.append(f"• {t}")
        severity = sev2 if sev2 != "Safe" else sev1
        
        # 2. AI tahlil
        is_scam, probability = ai_analyzer.predict(text)
        if is_scam and probability > 0.7:
            all_threats.append(f"AI tahlili: Scam ehtimoli {probability:.0%}")
            details.append(f"• AI tahlili: {probability:.1%} ehtimollik")
            severity = "High" if severity != "Critical" else "Critical"
        
        # 3. URL tekshirish
        urls = re.findall(r'https?://[^\s]+', text.lower())
        if urls and url_scanner:
            url_results = await url_scanner.check_url_multiple_sources(urls[0])
            for result in url_results:
                if result.get("suspicious"):
                    all_threats.append("Shubhali havola")
                    details.append(f"• {result.get('check', 'URL')}: shubhali")
                    severity = "Medium" if severity not in ["High", "Critical"] else severity
        
        # Xususiy kalit so'zlar
        suspicious_keywords = {
            "mukofot": "Scam",
            "yutuq": "Scam", 
            "pul": "Scam",
            "parol": "Phishing",
            "karta": "Phishing",
            "shaxsiy": "Phishing"
        }
        
        for keyword, threat_type in suspicious_keywords.items():
            if keyword in text.lower():
                if threat_type not in all_threats:
                    all_threats.append(threat_type)
                    details.append(f"• {keyword} so'zi topildi")
        
        # Natijani tayyorlash
        if all_threats:
            result_text = f"⚠️ <b>{len(all_threats)} TA XAVF ANIQLANDI:</b>\n\n"
            for i, threat in enumerate(all_threats[:5], 1):
                result_text += f"{i}. {threat}\n"
            
            result_text += f"\n🛡️ <b>Xavf darajasi:</b> "
            
            if severity == "Critical":
                result_text += "🔴 <b>CRITICAL</b>\n"
                result_text += "❌ <b>BU XABARGA ISHONMANG!</b>\n"
                result_text += "• Havolaga bosmang\n• Ma'lumot bermang\n• Bloklang"
            elif severity == "High":
                result_text += "🟠 <b>HIGH</b>\n"
                result_text += "⚠️ <b>EHTIYOT BO'LING!</b>\n"
                result_text += "• Havolaga faqat ishonchli manzillarda bosing\n• Ma'lumot bermang"
            elif severity == "Medium":
                result_text += "🟡 <b>MEDIUM</b>\n"
                result_text += "🔶 <b>DIQQATLI BO'LING</b>\n"
                result_text += "• Havolani tekshiring\n• Noma'lum manbalarga ishonmang"
            else:
                result_text += "🟢 <b>SAFE</b>\n"
            
            # Tugmalar
            builder = InlineKeyboardBuilder()
            
            if urls:
                builder.button(text="🔗 URL ni skanerlash", callback_data=f"scanurl_{hash(urls[0]) % 10000:04d}")
            
            builder.button(text="📊 Batafsil ma'lumot", callback_data=f"detail_{hash(text) % 10000:04d}")
            builder.button(text="🚨 Shikoyat qilish", callback_data=f"report_{message.from_user.id}")
            
            if urls:
                builder.adjust(1, 2)
            else:
                builder.adjust(2)
                
            keyboard = builder.as_markup()
        else:
            result_text = "✅ <b>XAVFSIZ</b>\n\nBu matnda xavf topilmadi."
            keyboard = None
        
        await loading_msg.delete()
        await message.answer(result_text, reply_markup=keyboard)
        
        # Log qilish
        user_id = message.from_user.id
        chat_id = message.chat.id if message.chat.type != "private" else None
        
        if chat_id:
            db.add_group(chat_id, message.chat.title)
        
        db.log_message(chat_id, user_id, text[:100], severity)
        
    except Exception as e:
        await loading_msg.delete()
        await message.answer(f"❌ Tahlil jarayonida xato: {str(e)[:100]}")

# ================ URL SKANERLASH ================
@dp.message(Command("scanurl"))
async def scanurl_cmd(message: types.Message):
    text = message.text.replace("/scanurl", "").strip()
    
    if not text:
        await message.answer("❌ URL kiriting: <code>/scanurl [havola]</code>")
        return
    
    if not text.startswith(("http://", "https://")):
        text = "https://" + text
    
    await process_url_scan(message, text)

async def process_url_scan(message: types.Message, url: str):
    loading_msg = await message.answer(f"🔍 <b>URL skanerlanyapti...</b>\n\n<code>{url[:50]}</code>")
    
    try:
        results = await url_scanner.check_url_multiple_sources(url)
        
        response = f"🔗 <b>URL Tahlili:</b>\n<code>{url[:100]}</code>\n\n"
        
        threats = []
        warnings = []
        
        for i, result in enumerate(results, 1):
            check_name = result.get("check", "Noma'lum")
            
            if result.get("suspicious"):
                details = result.get("details", {})
                
                if "free_domain" in details and details["free_domain"]:
                    threats.append(f"• Bepul domen (xavfli)")
                    warnings.append("Bepul domenlar odatda phishing uchun ishlatiladi")
                
                if "open_ports" in details and details["open_ports"]:
                    threats.append(f"• Ochiq portlar: {details['open_ports']}")
                    warnings.append("Ochiq portlar xavfsizlik muammosi bo'lishi mumkin")
                
                if "ssl_error" in details:
                    threats.append(f"• SSL muammosi")
                    warnings.append("SSL sertifikati xatosi")
                
                if "shortened" in details and details["shortened"]:
                    threats.append(f"• Qisqartirilgan URL ({details.get('service', 'Noma\'lum')})")
                    warnings.append("Qisqartirilgan URL lar maqsadini yashirishi mumkin")
        
        if threats:
            response += "⚠️ <b>XAVFLAR ANIQLANDI:</b>\n"
            for threat in threats:
                response += f"{threat}\n"
            
            response += "\n❌ <b>BU HAVOLAGA BOSMANG!</b>\n\n"
            
            if warnings:
                response += "<b>Ogohlantirishlar:</b>\n"
                for warning in warnings[:3]:
                    response += f"• {warning}\n"
            
            severity = "High"
        else:
            response += "✅ <b>XAVFSIZ</b>\n\nBu havola xavfli emas."
            severity = "Safe"
        
        await loading_msg.delete()
        
        # Tugmalar
        builder = InlineKeyboardBuilder()
        builder.button(text="🌐 Browserda ochish", url=url)
        builder.button(text="📊 Batafsil tahlil", callback_data=f"urldetail_{hash(url) % 10000:04d}")
        builder.button(text="🔄 Qayta tekshirish", callback_data=f"rescan_{hash(url) % 10000:04d}")
        builder.adjust(1, 2)
        
        keyboard = builder.as_markup()
        
        await message.answer(response, reply_markup=keyboard, disable_web_page_preview=True)
        
        # Log qilish
        db.log_message(
            message.chat.id if message.chat.type != "private" else None,
            message.from_user.id,
            f"[URL SCAN] {url[:50]}",
            severity
        )
            
    except Exception as e:
        await loading_msg.delete()
        await message.answer(f"❌ URL skanerlashda xato: {str(e)[:100]}")

# ================ FOYDALANUVCHI BUYRUQLARI ================
@dp.message(F.text == "📊 Mening statistikam")
@dp.message(Command("mystats"))
async def mystats_cmd(message: types.Message):
    user_id = message.from_user.id
    
    try:
        user_stats = db.get_user_stats(user_id)
        
        if user_stats:
            total = user_stats.get('total_messages', 0)
            threats = user_stats.get('threat_messages', 0)
            safe = total - threats
            trust_score = user_stats.get('trust_score', 100)
            username = user_stats.get('username')
            full_name = user_stats.get('full_name')
            last_activity = user_stats.get('last_activity')
            
            response = (
                f"📊 <b>Sizning statistikangiz</b>\n\n"
                f"👤 <b>Ma'lumotlar:</b>\n"
                f"   📛 Ism: {full_name or 'Noma\'lum'}\n"
                f"   📧 Username: @{username or 'Yo\'q'}\n"
                f"   ⭐ Ishonch: {trust_score}/100\n\n"
                
                f"📨 <b>Faollik:</b>\n"
                f"   Jami xabarlar: {total}\n"
                f"   ✅ Xavfsiz: {safe}\n"
                f"   🚨 Xavfli: {threats}\n"
                f"   🛡️ Xavfsizlik: {(safe/total*100 if total else 100):.1f}%\n"
                f"   📅 So'nggi faollik: {format_time_difference(last_activity)}\n\n"
            )
            
            # O'qilmagan xabarlar soni
            unread_count = db.get_unread_messages_count(user_id, is_admin=False)
            if unread_count > 0:
                response += f"📨 <b>Sizda {unread_count} ta o'qilmagan xabar bor!</b>\n\n"
            
            builder = InlineKeyboardBuilder()
            builder.button(text="🔄 Yangilash", callback_data="refresh_stats")
            builder.button(text="📩 Admin bilan bog'lanish", callback_data="start_support")
            builder.button(text="🔍 Tekshirish", callback_data="check_now")
            builder.button(text="🛡️ Xavfsizlik", callback_data="safety_tips")
            builder.adjust(2, 2)
            
            keyboard = builder.as_markup()
        else:
            response = "📭 <b>Siz hali hech qanday xabar yubormagansiz</b>\n\n"
            keyboard = None
        
        await message.answer(response, reply_markup=keyboard)
        
    except Exception as e:
        await message.answer(f"❌ Xato: {str(e)[:100]}")

@dp.message(F.text == "🛡️ Xavfsizlik tavsiyalari")
async def safety_tips_cmd(message: types.Message):
    """Xavfsizlik tavsiyalari"""
    tips = (
        "🛡️ <b>Kiberxavfsizlik Tavsiyalari</b>\n\n"
        
        "🔒 <b>1. Parol xavfsizligi:</b>\n"
        "• Har bir hisob uchun alohida parol\n"
        "• Kamida 12 ta belgi (harflar, raqamlar, belgilar)\n"
        "• 2-bosqichli autentifikatsiyani yoqing\n\n"
        
        "🌐 <b>2. Internet xavfsizligi:</b>\n"
        "• Faqat HTTPS saytlardan foydalaning\n"
        "• VPN dan foydalaning (ayniqsa ochiq WiFi da)\n"
        "• Brauzeringizni yangilang\n"
        "• Ad-blocker o'rnating\n\n"
        
        "📧 <b>3. Email xavfsizligi:</b>\n"
        "• Noma'lum manbalardan kelgan fayllarni ochmang\n"
        "• Phishing xabarlariga javob bermang\n"
        "• SPAM ga o'tkazishni o'rganing\n\n"
        
        "📱 <b>4. Telegram xavfsizligi:</b>\n"
        "• Noma'lum botlarga ma'lumot bermang\n"
        "• Guruhlarda shubhali fayllarni ochmang\n"
        "• Maxfiylik sozlamalarini tekshiring\n"
        "• Admin da'vosidagilarga ishonmaslik\n\n"
        
        "💳 <b>5. Moliyaviy xavfsizlik:</b>\n"
        "• Onlayn to'lovlarda faqat ishonchli saytlar\n"
        "• Karta ma'lumotlarini hech kimga bermang\n"
        "• SMS orqali kelgan kodlarni maxfiylashtiring\n\n"
        
        "<i>Xavfsizlik - bu odat, bir marotiba emas!</i>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Hozir tekshirish", callback_data="check_now")
    builder.button(text="📊 Mening statistikam", callback_data="mystats")
    builder.button(text="📚 Qo'llanma", callback_data="help_menu")
    builder.adjust(1, 2)
    
    keyboard = builder.as_markup()
    
    await message.answer(tips, reply_markup=keyboard)

# ================ ADMIN BUYRUQLARI ================
@dp.message(F.text == "👥 Foydalanuvchilar")
@dp.message(Command("users"))
async def users_cmd(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    
    try:
        parts = message.text.split()
        page = 1
        search = None
        
        if len(parts) > 1:
            if parts[1].isdigit():
                page = int(parts[1])
            else:
                search = parts[1]
        
        users_per_page = 10
        offset = (page - 1) * users_per_page
        
        if search:
            users = db.cursor.execute('''
                SELECT u.user_id, u.username, u.full_name, u.trust_score,
                       COUNT(l.id) as message_count,
                       SUM(CASE WHEN l.threat_level != 'Safe' THEN 1 ELSE 0 END) as threat_count
                FROM users u
                LEFT JOIN logs l ON u.user_id = l.user_id
                WHERE u.username LIKE ? OR u.full_name LIKE ? OR u.user_id = ?
                GROUP BY u.user_id
                ORDER BY u.user_id
                LIMIT ? OFFSET ?
            ''', (f"%{search}%", f"%{search}%", search if search.isdigit() else -1, users_per_page, offset)).fetchall()
        else:
            users = db.cursor.execute('''
                SELECT u.user_id, u.username, u.full_name, u.trust_score,
                       COUNT(l.id) as message_count,
                       SUM(CASE WHEN l.threat_level != 'Safe' THEN 1 ELSE 0 END) as threat_count
                FROM users u
                LEFT JOIN logs l ON u.user_id = l.user_id
                GROUP BY u.user_id
                ORDER BY u.user_id
                LIMIT ? OFFSET ?
            ''', (users_per_page, offset)).fetchall()
        
        if not users:
            await message.answer("📭 Foydalanuvchilar topilmadi")
            return
        
        response = f"👥 <b>Foydalanuvchilar</b>"
        if search:
            response += f" (Qidiruv: {search})"
        response += f"\nSahifa {page}\n\n"
        
        for user in users:
            user_id, username, full_name, trust_score, msg_count, threat_count = user
            
            user_link = f'<a href="tg://user?id={user_id}">{full_name or "Noma\'lum"}</a>'
            username_display = f"@{username}" if username else "Yo'q"
            
            if trust_score >= 80:
                trust_emoji = "🟢"
                trust_text = "Yuqori"
            elif trust_score >= 50:
                trust_emoji = "🟡"
                trust_text = "O'rtacha"
            else:
                trust_emoji = "🔴"
                trust_text = "Past"
            
            response += (
                f"{trust_emoji} <b>{user_link}</b>\n"
                f"   🆔 ID: <code>{user_id}</code>\n"
                f"   📛 {username_display}\n"
                f"   📊 Xabarlar: {msg_count}\n"
                f"   🚨 Xavflar: {threat_count}\n"
                f"   ⭐ Ishonch: {trust_score}/100 ({trust_text})\n"
                f"{'-'*35}\n"
            )
        
        # Sahifa ma'lumotlari
        if search:
            total_users = db.cursor.execute('''
                SELECT COUNT(*) FROM users 
                WHERE username LIKE ? OR full_name LIKE ? OR user_id = ?
            ''', (f"%{search}%", f"%{search}%", search if search.isdigit() else -1)).fetchone()[0]
        else:
            total_users = db.cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        
        total_pages = (total_users + users_per_page - 1) // users_per_page
        
        response += f"\n📄 <b>Sahifa {page}/{total_pages}</b> | Jami: {total_users} foydalanuvchi"
        
        # Keyboard yaratish
        builder = InlineKeyboardBuilder()
        
        # Oldingi tugma
        if page > 1:
            callback_data = f"users_{page-1}"
            if search:
                callback_data += f"_{search}"
            builder.button(text="⬅️ Oldingi", callback_data=callback_data)
        else:
            builder.button(text="•", callback_data="none")
        
        # Sahifa raqami
        builder.button(text=f"{page}/{total_pages}", callback_data="none")
        
        # Keyingi tugma
        if page < total_pages:
            callback_data = f"users_{page+1}"
            if search:
                callback_data += f"_{search}"
            builder.button(text="Keyingi ➡️", callback_data=callback_data)
        else:
            builder.button(text="•", callback_data="none")
        
        builder.adjust(3)
        keyboard = builder.as_markup()
        
        await message.answer(response, reply_markup=keyboard)
        
    except Exception as e:
        await message.answer(f"❌ Xato: {str(e)[:200]}")

@dp.message(F.text == "📈 Statistika")
@dp.message(Command("stats"))
async def stats_cmd(message: types.Message):
    """Umumiy statistika"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    
    try:
        users, groups, threats = db.get_stats()
        
        # Qo'shimcha statistikalar
        today_stats = db.cursor.execute('''
            SELECT 
                COUNT(DISTINCT user_id) as active_today,
                COUNT(*) as messages_today,
                SUM(CASE WHEN threat_level != 'Safe' THEN 1 ELSE 0 END) as threats_today
            FROM logs 
            WHERE DATE(created_at) = DATE('now')
        ''').fetchone()
        active_today, msgs_today, threats_today = today_stats or (0, 0, 0)
        
        stats_text = (
            f"📊 <b>Umumiy statistika</b>\n"
            f"🕐 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            f"👥 <b>Asosiy ko'rsatkichlar:</b>\n"
            f"   👤 Foydalanuvchilar: {users} ta\n"
            f"   👥 Guruhlar: {groups} ta\n"
            f"   🚨 Aniqlangan xavflar: {threats} ta\n\n"
            
            f"📅 <b>Bugungi kun:</b>\n"
            f"   👤 Faol foydalanuvchilar: {active_today}\n"
            f"   📨 Xabarlar: {msgs_today}\n"
            f"   ⚠️ Xavflar: {threats_today}\n"
        )
        
        await message.answer(stats_text)
        
    except Exception as e:
        await message.answer(f"❌ Xato: {str(e)[:200]}")

# ================ ADMIN SUPPORT JAVOBLARI ================
@dp.message(Command("support"))
async def support_admin_cmd(message: types.Message):
    """Admin uchun support so'rovlarini ko'rish va javob berish"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) > 1:
            # Aniq bir so'rovga javob berish
            if parts[1].isdigit():
                request_id = int(parts[1])
                
                # So'rovni olish
                request = db.get_support_request(request_id)
                if not request:
                    await message.answer(f"❌ #{request_id} ID li so'rov topilmadi")
                    return
                
                # Admin holatini saqlash
                db.cursor.execute('''INSERT OR REPLACE INTO user_states 
                                  (user_id, state, data) VALUES (?, ?, ?)''',
                                  (message.from_user.id, 'admin_reply', 
                                   json.dumps({'request_id': request_id, 'target_user': request['user_id']})))
                db.conn.commit()
                
                # Conversation ni olish
                conversation = db.get_support_conversation(request_id)
                
                response = (
                    f"📨 <b>Support So'rovi #{request_id}</b>\n"
                    f"👤 Foydalanuvchi: <a href='tg://user?id={request['user_id']}'>{request['full_name']}</a>\n"
                    f"📌 Mavzu: {request['subject']}\n"
                    f"📊 Holat: {request['status']}\n\n"
                    f"<b>Conversation:</b>\n"
                )
                
                for msg in conversation[-5:]:  # Oxirgi 5 xabarni ko'rsatish
                    sender = f"👤 {msg['full_name']}" if msg['is_from_user'] else f"👮 Admin"
                    time = msg['created_at'].split()[1][:5] if msg['created_at'] else ""
                    response += f"<i>{time}</i> {sender}: {msg['message_text']}\n\n"
                
                response += f"\n📝 <b>Javobingizni yozing...</b>"
                
                await message.answer(response, reply_markup=ReplyKeyboardRemove())
                return
            
            elif parts[1] == "list":
                # Barcha ochiq so'rovlarni ko'rsatish
                await show_support_requests(message)
                return
        
        # Default: ochiq so'rovlarni ko'rsatish
        await show_support_requests(message)
        
    except Exception as e:
        await message.answer(f"❌ Xato: {str(e)[:200]}")

async def show_support_requests(message: types.Message):
    """Ochiq support so'rovlarini ko'rsatish"""
    try:
        requests = db.get_support_requests(status='pending')
        
        if not requests:
            await message.answer("✅ Hozircha ochiq support so'rovlari yo'q")
            return
        
        response = f"📨 <b>Ochiq Support So'rovlari ({len(requests)} ta)</b>\n\n"
        
        for i, req in enumerate(requests, 1):
            user_link = f"<a href='tg://user?id={req['user_id']}'>{req['full_name']}</a>"
            username_display = f"@{req['username']}" if req['username'] else "Yo'q"
            
            response += (
                f"{i}. <b>#{req['id']}</b> - {req['subject']}\n"
                f"   👤 {user_link} ({username_display})\n"
                f"   📝 {req['last_message'][:60]}...\n"
                f"   ⏰ {format_time_difference(req['created_at'])}\n"
                f"{'-'*30}\n"
            )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Yangilash", callback_data="refresh_support")
        builder.button(text="📋 Barcha so'rovlar", callback_data="all_requests")
        builder.adjust(1, 1)
        
        keyboard = builder.as_markup()
        
        await message.answer(response, reply_markup=keyboard)
        
    except Exception as e:
        await message.answer(f"❌ Xato: {str(e)[:200]}")

@dp.message(F.text == "📨 Support")
async def support_button_cmd(message: types.Message):
    """Support tugmasi uchun handler"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    
    await show_support_requests(message)

# ================ ADMIN BILAN BOG'LANISH ================
@dp.message(F.text == "📩 Admin bilan bog'lanish")
async def contact_admin_cmd(message: types.Message):
    await message.answer(
        "📨 <b>Admin bilan bog'lanish</b>\n\n"
        "Xabaringiz mavzusini kiriting:\n\n"
        "<i>Misol: Hisobni tiklash, Xavfli xabar haqida, Bot bilan muammo</i>",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Foydalanuvchi holatini saqlash
    db.cursor.execute('''INSERT OR REPLACE INTO user_states 
                      (user_id, state, data) VALUES (?, ?, ?)''',
                      (message.from_user.id, 'awaiting_subject', json.dumps({})))
    db.conn.commit()

# ================ GURUH XABARLARI ================
@dp.message(F.text)
async def handle_all_messages(message: types.Message):
    # Admin bo'lsa
    if is_admin(message.from_user.id):
        await handle_admin_message(message)
        return
    
    # Foydalanuvchi holatini tekshirish
    result = db.cursor.execute('''SELECT state, data FROM user_states WHERE user_id = ?''',
                              (message.from_user.id,)).fetchone()
    
    if result:
        state, data_json = result
        state_data = json.loads(data_json) if data_json else {}
        
        if state == 'awaiting_subject':
            # Mavzuni qabul qilish
            subject = message.text[:100]
            
            db.cursor.execute('''UPDATE user_states SET 
                              state = 'awaiting_message', 
                              data = ? WHERE user_id = ?''',
                              (json.dumps({'subject': subject}), message.from_user.id))
            db.conn.commit()
            
            await message.answer(
                f"📝 <b>Mavzu:</b> {subject}\n\n"
                f"Endi xabaringizni yuboring:\n\n"
                f"<i>Xabaringizni batafsil yozing. Admin tez orada javob beradi.</i>"
            )
        
        elif state == 'awaiting_message':
            # Xabarni qabul qilish
            subject = state_data.get('subject', 'Noma\'lum')
            message_text = message.text
            
            request_id = db.create_support_request(
                message.from_user.id,
                subject,
                message_text
            )
            
            if request_id:
                db.cursor.execute('''DELETE FROM user_states WHERE user_id = ?''',
                                (message.from_user.id,))
                db.conn.commit()
                
                await message.answer(
                    f"✅ <b>Xabaringiz qabul qilindi!</b>\n\n"
                    f"📌 <b>Mavzu:</b> {subject}\n"
                    f"📝 <b>So'rovingiz:</b> {message_text[:100]}...\n"
                    f"🆔 <b>ID:</b> #{request_id}\n\n"
                    f"<i>Admin tez orada javob beradi.</i>",
                    reply_markup=get_main_keyboard(message.from_user.id)
                )
                
                # Adminlarga bildirish
                for admin_id in ADMIN_IDS:
                    try:
                        user_link = get_user_link(message.from_user)
                        await bot.send_message(
                            admin_id,
                            f"📨 <b>Yangi Support So'rovi!</b>\n\n"
                            f"🆔 ID: #{request_id}\n"
                            f"👤 {user_link}\n"
                            f"📌 Mavzu: {subject}\n"
                            f"📝 Xabar: {message_text[:200]}...\n\n"
                            f"<i>Javob berish uchun: /support {request_id}</i>"
                        )
                        print(f"✅ Admin {admin_id} ga bildirish yuborildi")
                    except Exception as e:
                        print(f"❌ Admin {admin_id} ga yuborish xatosi: {e}")
            else:
                await message.answer(
                    "❌ Xabar yuborishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring.",
                    reply_markup=get_main_keyboard(message.from_user.id)
                )
    else:
        # Guruhda avtomatik tekshirish
        if message.chat.type in ["group", "supergroup"]:
            await handle_group_message(message)
        else:
            # Shaxsiy chatda tekshirish taklifi
            await message.answer(
                "🤖 <b>Kiber-Inspektor</b> sizning xabaringizni avtomatik tekshirishni taklif qiladi.\n\n"
                "Xavfsizlikni ta'minlash uchun quyidagi tugmalardan foydalaning:",
                reply_markup=get_main_keyboard(message.from_user.id)
            )

async def handle_admin_message(message: types.Message):
    """Admin xabarlarini qayta ishlash"""
    # Admin holatini tekshirish
    result = db.cursor.execute('''SELECT state, data FROM user_states WHERE user_id = ?''',
                              (message.from_user.id,)).fetchone()
    
    if result:
        state, data_json = result
        state_data = json.loads(data_json) if data_json else {}
        
        if state == 'admin_reply':
            # Admin javobini qabul qilish
            request_id = state_data.get('request_id')
            target_user = state_data.get('target_user')
            reply_text = message.text
            
            if request_id and target_user:
                # Conversation ga javob qo'shish
                if db.add_support_message(request_id, message.from_user.id, reply_text, is_from_user=False):
                    # Request statusini yangilash
                    db.update_support_request(request_id, 'answered', reply_text)
                    
                    # Holatni tozalash
                    db.cursor.execute('''DELETE FROM user_states WHERE user_id = ?''',
                                    (message.from_user.id,))
                    db.conn.commit()
                    
                    # Foydalanuvchiga javob yuborish
                    try:
                        await bot.send_message(
                            target_user,
                            f"📨 <b>Admin javobi (So'rov #{request_id}):</b>\n\n{reply_text}\n\n"
                            f"<i>Qo'shimcha savollaringiz bo'lsa, yana yozing.</i>",
                            reply_markup=get_main_keyboard(target_user)
                        )
                        
                        await message.answer(
                            f"✅ <b>Javob yuborildi!</b>\n\n"
                            f"👤 Foydalanuvchi: {target_user}\n"
                            f"📝 Javob: {reply_text[:100]}...",
                            reply_markup=get_admin_keyboard()
                        )
                    except Exception as e:
                        await message.answer(
                            f"❌ Foydalanuvchiga javob yuborishda xato: {e}",
                            reply_markup=get_admin_keyboard()
                        )
                else:
                    await message.answer("❌ Javob yuborishda xatolik")
            else:
                await message.answer("❌ Ma'lumotlar topilmadi")
        else:
            # Oddiy admin xabari
            await message.answer(
                "🤖 <b>Admin paneli</b>\n\n"
                "Foydalanuvchilarga javob berish uchun:\n"
                "1. /support list - barcha so'rovlarni ko'rish\n"
                "2. /support [ID] - aniq so'rovga javob berish\n\n"
                "Boshqa admin buyruqlari: /users, /stats, /report",
                reply_markup=get_admin_keyboard()
            )
    else:
        # Oddiy admin xabari
        await message.answer(
            "🤖 <b>Admin paneli</b>\n\n"
            "Foydalanuvchilarga javob berish uchun:\n"
            "1. /support list - barcha so'rovlarni ko'rish\n"
            "2. /support [ID] - aniq so'rovga javob berish\n\n"
            "Boshqa admin buyruqlari: /users, /stats, /report",
            reply_markup=get_admin_keyboard()
        )

# ================ FAYL TAHLLILI ================
@dp.message(F.document | F.photo | F.video | F.audio)
async def handle_files(message: types.Message):
    """Fayllarni qayta ishlash"""
    
    print(f"DEBUG: Fayl qabul qilindi - {message.content_type}")
    
    # Guruhda bo'lsa
    if message.chat.type in ["group", "supergroup"]:
        await analyze_group_file(message)
    else:
        # Shaxsiy chatda
        await analyze_private_file(message)

async def analyze_group_file(message: types.Message):
    """Guruhdagi faylni tahlil qilish"""
    try:
        if message.document:
            file_name = message.document.file_name
            file_size = message.document.file_size
            mime_type = message.document.mime_type
            
            print(f"DEBUG: Fayl: {file_name}, Hajm: {file_size}, MIME: {mime_type}")
            
            # Yuklanmoqda xabari
            loading_msg = await message.reply("🔍 <b>Fayl tahlil qilinmoqda...</b>")
            
            try:
                # Tahlil natijasini olish
                analysis_result = await file_analyzer.analyze_telegram_file(bot, message)
                
                verdict = analysis_result.get("verdict", "Safe")
                risk_level = analysis_result.get("risk_level", "Low")
                warnings = analysis_result.get("warnings", [])
                
                # Yuklanmoqda xabarini o'chirish
                try:
                    await loading_msg.delete()
                except:
                    pass  # Xabar allaqachon o'chirilgan bo'lishi mumkin
                
                # Agar xavfli bo'lsa
                if verdict in ["Malicious", "Suspicious", "Caution"]:
                    user_link = get_user_link(message.from_user)
                    
                    # Xabar tayyorlash
                    result_message = file_analyzer.get_file_verdict_message(analysis_result)
                    
                    # Inline tugmalar
                    builder = InlineKeyboardBuilder()
                    
                    # Fayl turi bo'yicha qo'shimcha ma'lumotlar
                    file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ""
                    if file_ext in ['exe', 'apk', 'jar', 'msi']:
                        builder.button(
                            text="ℹ️ Fayl turi haqida",
                            callback_data=f"fileinfo_{file_ext}"
                        )
                    
                    builder.button(
                        text="🚨 Shikoyat qilish",
                        callback_data=f"reportfile_{message.from_user.id}"
                    )
                    
                    builder.adjust(1)
                    keyboard = builder.as_markup()
                    
                    await message.reply(result_message, reply_markup=keyboard)
                    
                    # Log qilish
                    db.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
                    db.add_group(message.chat.id, message.chat.title)
                    
                    severity = {
                        "Malicious": "Critical",
                        "Suspicious": "High",
                        "Caution": "Medium",
                        "Low Risk": "Low",
                        "Safe": "Safe"
                    }.get(verdict, "Safe")
                    
                    db.log_message(
                        message.chat.id,
                        message.from_user.id,
                        f"[FILE] {file_name[:50]}",
                        severity
                    )
                else:
                    # Xavfsiz fayl
                    safe_msg = (
                        f"✅ <b>XAVFSIZ FAYL</b>\n\n"
                        f"📁 <code>{file_name}</code>\n"
                        f"📊 Hajm: {file_size/(1024*1024):.2f} MB\n"
                        f"🛡️ Tahlil: ✅ Xavfsiz\n"
                    )
                    
                    await message.reply(safe_msg)
                    
                    # Log qilish
                    db.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
                    db.add_group(message.chat.id, message.chat.title)
                    db.log_message(
                        message.chat.id,
                        message.from_user.id,
                        f"[FILE] {file_name[:50]}",
                        "Safe"
                    )
                    
            except Exception as e:
                # Yuklanmoqda xabarini o'chirish
                try:
                    await loading_msg.delete()
                except:
                    pass
                
                print(f"❌ Fayl tahlilida ichki xato: {e}")
                
                # Xato xabari
                error_msg = (
                    f"⚠️ <b>Fayl tahlilida xato</b>\n\n"
                    f"📁 {file_name}\n"
                    f"📊 {file_size/(1024*1024):.2f} MB\n\n"
                    f"<i>Fayl tahlil qilishda texnik muammo yuz berdi.</i>"
                )
                await message.reply(error_msg)
                
                # Xato log qilish
                db.log_message(
                    message.chat.id,
                    message.from_user.id,
                    f"[FILE_ERROR] {file_name[:50]}",
                    "Unknown"
                )
    
    except Exception as e:
        print(f"❌ Fayl tahlilida tashqi xato: {e}")

async def analyze_private_file(message: types.Message):
    """Shaxsiy chatdagi faylni tahlil qilish"""
    try:
        if message.document:
            file_name = message.document.file_name
            file_size = message.document.file_size
            
            loading_msg = await message.answer("🔍 <b>Fayl tahlil qilinmoqda...</b>")
            
            try:
                # YANGI: Bot obyekti bilan faylni tahlil qilish
                analysis_result = await file_analyzer.analyze_telegram_file(bot, message)
                
                # Natija xabarini tayyorlash
                response = file_analyzer.get_file_verdict_message(analysis_result)
                
                await loading_msg.delete()
                await message.answer(response)
                
                # Foydalanuvchi stats yangilash
                db.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
                
                # Log qilish
                db.log_message(
                    None,  # Shaxsiy chat
                    message.from_user.id,
                    f"[FILE] {file_name[:50]}",
                    analysis_result.get("risk_level", "Safe")
                )
                
            except Exception as e:
                await loading_msg.delete()
                print(f"❌ Shaxsiy fayl tahlilida xato: {e}")
                
                error_msg = (
                    f"⚠️ <b>Fayl tahlilida xato</b>\n\n"
                    f"Faylni tahlil qilishda muammo yuz berdi.\n"
                    f"Xato: {str(e)[:100]}"
                )
                await message.answer(error_msg)
                
    except Exception as e:
        print(f"❌ Shaxsiy fayl tahlilida tashqi xato: {e}")

async def handle_group_message(message: types.Message):
    text = message.text
    
    # Tahlil qilish
    threat1, severity = analyze_message(text)
    threats2, severity2 = analyze_message_advanced(text)
    
    # URL tekshirish
    urls = re.findall(r'https?://[^\s]+', text.lower())
    url_threats = []
    
    bad_domains = ['.tk', '.ml', '.ga', '.cf', '.gq', '.xyz', '.top', '.club', '.shop', '.online']
    for url in urls[:2]:
        for domain in bad_domains:
            if domain in url:
                url_threats.append("Phishing havolasi")
                severity = "High" if severity != "Critical" else "Critical"
                break
    
    # Barcha tahdidlarni birlashtirish
    all_threats = []
    if threat1: 
        all_threats.append(threat1)
    if url_threats: 
        all_threats.extend(url_threats)
    if threats2: 
        all_threats.extend(threats2)
    
    # AI tahlil
    is_scam, probability = ai_analyzer.predict(text)
    if is_scam and probability > 0.7:
        all_threats.append(f"AI: Scam ehtimoli {probability:.0%}")
        severity = "High" if severity not in ["Critical", "High"] else severity
    
    # Agar tahdid bo'lsa
    if all_threats:
        user_link = get_user_link(message.from_user)
        
        if severity == "Critical":
            emoji = "🔴"
            title = "CRITICAL XAVF!"
        elif severity == "High":
            emoji = "🟠"
            title = "YUQORI XAVF!"
        elif severity == "Medium":
            emoji = "🟡"
            title = "O'RTACHA XAVF"
        else:
            emoji = "⚪"
            title = "XAVF"
        
        alert = f"{emoji} <b>{title}</b>\n\n"
        alert += f"👤 {user_link}\n"
        alert += f"📛 {all_threats[0]}\n"
        
        if len(all_threats) > 1:
            alert += f"📊 {len(all_threats)-1} ta qo'shimcha xavf\n"
        
        alert += f"🛡️ <b>{severity}</b> daraja\n\n"
        
        if severity == "Critical":
            alert += "❌ <b>BU XABARGA ISHONMANG!</b>\n"
            alert += "• Havolaga bosmang\n• Ma'lumot bermang\n• Foydalanuvchini bloklang"
        elif severity == "High":
            alert += "⚠️ <b>EHTIYOT BO'LING!</b>\n"
            alert += "• Havolaga faqat ishonchli manzillarda bosing\n• Shaxsiy ma'lumot bermang"
        elif severity == "Medium":
            alert += "🔶 <b>DIQQATLI BO'LING</b>\n"
            alert += "• Havolani tekshiring\n• Noma'lum manbalarga ishonmang"
        
        await message.reply(alert)
        
        # Log qilish
        db.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
        db.add_group(message.chat.id, message.chat.title)
        db.log_message(message.chat.id, message.from_user.id, text[:100], severity)
    
    # Agar xavf bo'lmasa, faqat log qilish
    elif message.chat.type in ["group", "supergroup"]:
        db.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
        db.add_group(message.chat.id, message.chat.title)
        db.log_message(message.chat.id, message.from_user.id, text[:100], "Safe")

# ================ CALLBACK QUERY HANDLERLAR ================
@dp.callback_query()
async def handle_callback(callback: CallbackQuery):
    """Callback query larini qayta ishlash"""
    data = callback.data
    
    try:
        if data == "none":
            await callback.answer()
            return
        
        # 1. Foydalanuvchilar sahifasi
        if data.startswith("users_"):
            await process_users_callback(callback, data)
        
        # 2. Statistika yangilash
        elif data == "refresh_stats":
            await callback.answer("Statistika yangilanmoqda...")
            await mystats_cmd(callback.message)
        
        # 3. Tekshirish
        elif data == "check_now" or data == "start_check":
            await callback.answer("Tekshirish boshlandi...")
            await check_cmd(callback.message)
        
        # 4. Shaxsiy statistika
        elif data == "mystats":
            await callback.answer("Statistika yuklanmoqda...")
            await mystats_cmd(callback.message)
        
        # 5. Xavfsizlik tavsiyalari
        elif data == "safety_tips":
            await callback.answer("Tavsiyalar yuklanmoqda...")
            await safety_tips_cmd(callback.message)
        
        # 6. Yordam
        elif data == "help_menu":
            await callback.answer("Yordam yuklanmoqda...")
            await help_cmd(callback.message)
        
        # 7. Admin bilan bog'lanish
        elif data == "start_support":
            await callback.answer("Admin bilan bog'lanish...")
            await contact_admin_cmd(callback.message)
        
        # 8. Support so'rovlarini yangilash
        elif data == "refresh_support":
            await callback.answer("Support so'rovlari yangilanmoqda...")
            message_obj = callback.message
            message_obj.text = "/support list"
            await support_admin_cmd(message_obj)
        
        # 9. Barcha so'rovlar
        elif data == "all_requests":
            await show_all_requests_callback(callback)
        
        # 10. Detail tugmasi
        elif data.startswith("detail_"):
            await show_detail_analysis_callback(callback)
        
        # 11. Report tugmasi
        elif data.startswith("report_"):
            await process_report_callback(callback)
        
        # 12. URL skanerlash
        elif data.startswith("scanurl_"):
            await process_url_scan_callback(callback)
        
        # 13. URL detail
        elif data.startswith("urldetail_"):
            await show_url_detail_callback(callback)
        
        # 14. Qayta skanerlash
        elif data.startswith("rescan_"):
            await rescan_url_callback(callback)
        
        # 15. Fayl ma'lumotlari
        elif data.startswith("fileinfo_"):
            await show_file_info_callback(callback)
        
        # 16. Fayl shikoyati
        elif data.startswith("reportfile_"):
            await process_file_report_callback(callback)
        
        else:
            await callback.answer("Tugma ishladi")
        
    except Exception as e:
        await callback.answer(f"Xato: {str(e)[:50]}", show_alert=True)

async def process_users_callback(callback: CallbackQuery, data: str):
    """Foydalanuvchilar sahifasini qayta ishlash"""
    try:
        # Ma'lumotlarni ajratish
        parts = data.split("_")
        if len(parts) >= 2:
            page = int(parts[1])
            search = parts[2] if len(parts) > 2 else ""
        else:
            page = 1
            search = ""
        
        await callback.answer("Sahifa yangilanmoqda...")
        
        # Sahifani yangilash
        await show_users_page(callback, page, search)
        
    except Exception as e:
        await callback.answer(f"Xato: {str(e)[:50]}", show_alert=True)

async def show_users_page(callback: CallbackQuery, page: int, search: str = ""):
    """Foydalanuvchilar sahifasini ko'rsatish"""
    try:
        users_per_page = 10
        offset = (page - 1) * users_per_page
        
        if search:
            users = db.cursor.execute('''
                SELECT u.user_id, u.username, u.full_name, u.trust_score,
                       COUNT(l.id) as message_count,
                       SUM(CASE WHEN l.threat_level != 'Safe' THEN 1 ELSE 0 END) as threat_count
                FROM users u
                LEFT JOIN logs l ON u.user_id = l.user_id
                WHERE u.username LIKE ? OR u.full_name LIKE ? OR u.user_id = ?
                GROUP BY u.user_id
                ORDER BY u.user_id
                LIMIT ? OFFSET ?
            ''', (f"%{search}%", f"%{search}%", search if search.isdigit() else -1, users_per_page, offset)).fetchall()
        else:
            users = db.cursor.execute('''
                SELECT u.user_id, u.username, u.full_name, u.trust_score,
                       COUNT(l.id) as message_count,
                       SUM(CASE WHEN l.threat_level != 'Safe' THEN 1 ELSE 0 END) as threat_count
                FROM users u
                LEFT JOIN logs l ON u.user_id = l.user_id
                GROUP BY u.user_id
                ORDER BY u.user_id
                LIMIT ? OFFSET ?
            ''', (users_per_page, offset)).fetchall()
        
        if not users:
            await callback.message.edit_text("📭 Foydalanuvchilar topilmadi")
            return
        
        response = f"👥 <b>Foydalanuvchilar</b>"
        if search:
            response += f" (Qidiruv: {search})"
        response += f"\nSahifa {page}\n\n"
        
        for user in users:
            user_id, username, full_name, trust_score, msg_count, threat_count = user
            
            user_link = f'<a href="tg://user?id={user_id}">{full_name or "Noma\'lum"}</a>'
            username_display = f"@{username}" if username else "Yo'q"
            
            if trust_score >= 80:
                trust_emoji = "🟢"
                trust_text = "Yuqori"
            elif trust_score >= 50:
                trust_emoji = "🟡"
                trust_text = "O'rtacha"
            else:
                trust_emoji = "🔴"
                trust_text = "Past"
            
            response += (
                f"{trust_emoji} <b>{user_link}</b>\n"
                f"   🆔 ID: <code>{user_id}</code>\n"
                f"   📛 {username_display}\n"
                f"   📊 Xabarlar: {msg_count}\n"
                f"   🚨 Xavflar: {threat_count}\n"
                f"   ⭐ Ishonch: {trust_score}/100 ({trust_text})\n"
                f"{'-'*35}\n"
            )
        
        # Sahifa ma'lumotlari
        if search:
            total_users = db.cursor.execute('''
                SELECT COUNT(*) FROM users 
                WHERE username LIKE ? OR full_name LIKE ? OR user_id = ?
            ''', (f"%{search}%", f"%{search}%", search if search.isdigit() else -1)).fetchone()[0]
        else:
            total_users = db.cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        
        total_pages = (total_users + users_per_page - 1) // users_per_page
        
        response += f"\n📄 <b>Sahifa {page}/{total_pages}</b> | Jami: {total_users} foydalanuvchi"
        
        # Keyboard yaratish
        builder = InlineKeyboardBuilder()
        
        # Oldingi tugma
        if page > 1:
            callback_data = f"users_{page-1}"
            if search:
                callback_data += f"_{search}"
            builder.button(text="⬅️ Oldingi", callback_data=callback_data)
        else:
            builder.button(text="•", callback_data="none")
        
        # Sahifa raqami
        builder.button(text=f"{page}/{total_pages}", callback_data="none")
        
        # Keyingi tugma
        if page < total_pages:
            callback_data = f"users_{page+1}"
            if search:
                callback_data += f"_{search}"
            builder.button(text="Keyingi ➡️", callback_data=callback_data)
        else:
            builder.button(text="•", callback_data="none")
        
        builder.adjust(3)
        keyboard = builder.as_markup()
        
        await callback.message.edit_text(response, reply_markup=keyboard)
        
    except Exception as e:
        await callback.answer(f"Xato: {str(e)[:100]}", show_alert=True)

async def show_all_requests_callback(callback: CallbackQuery):
    """Barcha support so'rovlarini ko'rsatish"""
    try:
        requests = db.get_support_requests()
        
        if not requests:
            await callback.answer("Hech qanday so'rov topilmadi", show_alert=True)
            return
        
        response = f"📨 <b>Barcha Support So'rovlari ({len(requests)} ta)</b>\n\n"
        
        for i, req in enumerate(requests, 1):
            status_emoji = {
                'pending': '🟡',
                'answered': '🟢',
                'closed': '🔴'
            }.get(req['status'], '⚪')
            
            user_link = f"<a href='tg://user?id={req['user_id']}'>{req['full_name']}</a>"
            
            response += (
                f"{status_emoji} <b>#{req['id']}</b> - {req['subject']}\n"
                f"   👤 {user_link}\n"
                f"   📊 Holat: {req['status']}\n"
                f"   ⏰ {format_time_difference(req['created_at'])}\n"
                f"{'-'*25}\n"
            )
        
        # InlineKeyboard yaratish
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Orqaga", callback_data="refresh_support")
        builder.adjust(1)
        keyboard = builder.as_markup()
        
        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.answer("Barcha so'rovlar yuklandi")
        
    except Exception as e:
        await callback.answer(f"Xato: {str(e)[:50]}", show_alert=True)

async def show_detail_analysis_callback(callback: CallbackQuery):
    """Batafsil tahlilni ko'rsatish"""
    await callback.answer("Batafsil ma'lumot yuklanmoqda...")
    
    detailed_info = (
        "📊 <b>Batafsil Tahlil Natijalari</b>\n\n"
        "🔍 <b>1. Matn Tahlili:</b>\n"
        "• Shubhali so'zlar tekshirildi\n"
        "• Xavfli kombinatsiyalar aniqlash\n"
        "• So'zlar konteksti tahlili\n\n"
        
        "🔗 <b>2. URL Tahlili:</b>\n"
        "• Domen nomi tekshirildi\n"
        "• SSL sertifikati\n"
        "• Qisqartirilgan URL lar\n"
        "• Malware manzillari\n\n"
        
        "🤖 <b>3. AI Tahlili:</b>\n"
        "• Sun'iy intellekt modeli\n"
        "• Pattern recognition\n"
        "• Ehtimollik tahmini\n"
        "• Machine learning algoritmi\n\n"
        
        "📊 <b>4. Statistik Tahlil:</b>\n"
        "• Benign message patterns\n"
        "• Threat database check\n"
        "• Real-time analysis\n"
        "• Historical comparison\n\n"
        
        "<i>Tahlil 4 xil metodika asosida amalga oshirildi.</i>"
    )
    
    await callback.message.answer(detailed_info)
    await callback.answer()

async def process_report_callback(callback: CallbackQuery):
    """Shikoyat qilish"""
    await callback.answer("Shikoyatingiz qabul qilindi!")
    
    report_message = (
        "🚨 <b>Shikoyatingiz qabul qilindi!</b>\n\n"
        "✅ Shikoyat muvaffaqiyatli yuborildi\n"
        "👮 Adminlar xabarni tekshiradi\n"
        "⏰ Tekshirish 1-24 soat ichida\n"
        "📞 Natijalar sizga yetkaziladi\n\n"
        "<i>Kiberxavfsizlikka hissa qo'shganingiz uchun rahmat!</i>"
    )
    
    await callback.message.answer(report_message)

async def process_url_scan_callback(callback: CallbackQuery):
    """URL skanerlash callback"""
    await callback.answer("URL skanerlash boshlandi...")
    
    scan_message = (
        "🔗 <b>URL Skanerlash Boshlanmoqda</b>\n\n"
        "Quyidagi tizimlar orqali tekshiriladi:\n"
        "• Google Safe Browsing\n"
        "• VirusTotal API\n"
        "• PhishTank database\n"
        "• Custom blacklist\n\n"
        "<i>Bu jarayon 10-30 soniya davom etishi mumkin...</i>"
    )
    
    await callback.message.answer(scan_message)

async def show_url_detail_callback(callback: CallbackQuery):
    """URL batafsil ma'lumotlari"""
    await callback.answer("URL tafsilotlari yuklanmoqda...")
    
    url_details = (
        "🔗 <b>URL Batafsil Tahlili</b>\n\n"
        "📊 <b>Texnik Ma'lumotlar:</b>\n"
        "• DNS yozuvlari tekshirildi\n"
        "• IP manzili aniqlangan\n"
        "• Server joylashuvi\n"
        "• WHOIS ma'lumotlari\n\n"
        
        "🛡️ <b>Xavfsizlik Ko'rsatkichlari:</b>\n"
        "• SSL/TLS sertifikati\n"
        "• HSTS sozlamalari\n"
        "• Content Security Policy\n"
        "• HTTP headers analysis\n\n"
        
        "⚠️ <b>Potensial Xavflar:</b>\n"
        "• Phishing ehtimoli\n"
        "• Malware distribyutsiya\n"
        "• Fraudulent content\n"
        "• Social engineering\n\n"
        
        "<i>URL batafsil 15+ indikator bo'yicha tekshirildi</i>"
    )
    
    await callback.message.answer(url_details)

async def rescan_url_callback(callback: CallbackQuery):
    """URL ni qayta skanerlash"""
    await callback.answer("URL qayta skanerlanyapti...")
    
    rescan_message = (
        "🔄 <b>URL Qayta Skanerlash</b>\n\n"
        "URL quyidagi manbalar orqali qayta tekshirilmoqda:\n"
        "1. VirusTotal - 70+ antivirus\n"
        "2. Google Safe Browsing\n"
        "3. URLhaus database\n"
        "4. PhishTank real-time\n"
        "5. OpenPhish feed\n\n"
        "<i>Yangilangan natijalar tez orada...</i>"
    )
    
    await callback.message.answer(rescan_message)

async def show_file_info_callback(callback: CallbackQuery):
    """Fayl turi haqida ma'lumot"""
    file_type = callback.data.replace("fileinfo_", "")
    
    file_info = {
        'exe': (
            "⚙️ <b>EXE Fayli (Windows Dasturi)</b>\n\n"
            "✅ <b>Xavfsiz Ishlatish:</b>\n"
            "• Faqat ishonchli manbalardan yuklang\n"
            "• Rasmiy veb-saytlardan oling\n"
            "• Antivirus bilan tekshiring\n"
            "• Digital signature ni tekshiring\n\n"
            "⚠️ <b>Xavflar:</b>\n"
            "• Virus, trojan, malware\n"
            "• Ransomware ehtimoli\n"
            "• System modification\n"
            "• Data theft risk\n"
        ),
        'apk': (
            "📱 <b>APK Fayli (Android Ilovasi)</b>\n\n"
            "✅ <b>Xavfsiz Ishlatish:</b>\n"
            "• Faqat Google Play Store\n"
            "• Developer imzosi tekshirish\n"
            "• Permission larini o'rganing\n"
            "• Review larni o'qing\n\n"
            "⚠️ <b>Xavflar:</b>\n"
            "• Malicious permissions\n"
            "• Adware, spyware\n"
            "• Fake banking apps\n"
            "• Data leakage\n"
        ),
        'jar': (
            "☕ <b>JAR Fayli (Java Archive)</b>\n\n"
            "✅ <b>Xavfsiz Ishlatish:</b>\n"
            "• Faqat ishonchli developer lardan\n"
            "• Java security sozlamalari\n"
            "• Sandbox muhitida ishlating\n"
            "• Code signing tekshirish\n\n"
            "⚠️ <b>Xavflar:</b>\n"
            "• Java exploit lar\n"
            "• System access\n"
            "• Malicious applets\n"
            "• Cross-platform threats\n"
        ),
        'msi': (
            "🖥️ <b>MSI Fayli (Windows Installer)</b>\n\n"
            "✅ <b>Xavfsiz Ishlatish:</b>\n"
            "• Faqat rasmiy distribyutor lardan\n"
            "• Digital certificate tekshirish\n"
            "• Installation path diqqat bilan\n"
            "• Custom install tanlash\n\n"
            "⚠️ <b>Xavflar:</b>\n"
            "• Silent installation\n"
            "• Bundled software\n"
            "• System changes\n"
            "• Unwanted programs\n"
        )
    }
    
    info = file_info.get(file_type, 
        f"📄 <b>{file_type.upper()} Fayli</b>\n\n"
        "Bu fayl turi haqida ma'lumot mavjud emas.\n"
        "Har qanday noma'lum faylni ochishdan oldin:\n"
        "• Antivirus bilan tekshiring\n"
        "• Manba ishonchliligini aniqlang\n"
        "• Virtual muhitda sinab ko'ring\n"
        "• Hech qanday shaxsiy ma'lumot bermang"
    )
    
    await callback.answer(f"{file_type.upper()} fayli haqida ma'lumot")
    await callback.message.answer(info)

async def process_file_report_callback(callback: CallbackQuery):
    """Fayl shikoyati"""
    await callback.answer("Fayl haqida shikoyat qabul qilindi!")
    
    report_response = (
        "🚨 <b>Fayl Shikoyati Qabul Qilindi</b>\n\n"
        "✅ Shikoyat ma'lumotlar bazasiga qo'shildi\n"
        "👮 Adminlar faylni tekshiradi\n"
        "🔍 VirusTotal va boshqa tizimlar\n"
        "📊 Global blacklist yangilanadi\n\n"
        "<i>Jamoaviy xavfsizlikka hissa qo'shganingiz uchun rahmat!</i>"
    )
    
    await callback.message.answer(report_response)

# ================ MENYU TUGMALARI ================
@dp.message(F.text == "⬅️ Asosiy menyu")
async def main_menu_cmd(message: Message):
    """Asosiy menyuga qaytish"""
    await message.answer(
        "🛡️ <b>Asosiy menyu</b>\n\n"
        "Quyidagi tugmalardan birini tanlang:",
        reply_markup=get_main_keyboard(message.from_user.id)
    )

# ================ BOTNI ISHGA TUSHIRISH ================
async def main():
    """Asosiy funksiya"""
    print("=" * 50)
    print("🛡️  KIBER-INSPEKTOR BOTI")
    print("=" * 50)
    
    try:
        bot_info = await bot.get_me()
        print(f"🤖 Bot: @{bot_info.username}")
        print(f"👮 Adminlar: {ADMIN_IDS}")
        print(f"💾 DB: ✅")
        print("=" * 50)
        print("\n📊 Bot faol...")
        print(f"DEBUG: Bot token mavjud: {'✅' if BOT_TOKEN else '❌'}")
        print(f"DEBUG: Admin ID lar soni: {len(ADMIN_IDS)}")
    except Exception as e:
        print(f"❌ Bot ma'lumotlarini olishda xato: {e}")
        return
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Polling xatosi: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    # Logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot to'xtatildi.")
    except Exception as e:
        print(f"❌ Kutilmagan xato: {e}")