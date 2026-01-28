# utils/helpers.py
"""
Umumiy yordamchi funksiyalar: fayl tozalash, statistika formatlash, admin tekshiruvi va boshqalar.
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from config import config

logger = logging.getLogger(__name__)

def cleanup_temp_file(file_path: str) -> None:
    """
    Temp faylni o'chirish (diskni to'ldirmaslik uchun).
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Temp fayl o'chirildi: {file_path}")
    except Exception as e:
        logger.warning(f"Temp faylni o'chirishda xato: {file_path} → {e}")


def cleanup_temp_directory() -> None:
    """
    Butun temp papkani tozalash (bot restartida yoki cron job orqali chaqirilishi mumkin).
    """
    if not os.path.exists(config.TEMP_DIR):
        return

    for filename in os.listdir(config.TEMP_DIR):
        file_path = os.path.join(config.TEMP_DIR, filename)
        if os.path.isfile(file_path):
            cleanup_temp_file(file_path)


def format_stats_message(
    stats: tuple[int, int, int],
    daily_stats: List[Dict[str, Any]],
    recent_threats: List[Dict[str, Any]]
) -> str:
    """
    Statistika ma'lumotlarini chiroyli matn sifatida formatlash.
    """
    users, groups, threats = stats

    text = "<b>Bot statistikasi:</b>\n\n"
    text += f"• Jami foydalanuvchilar: <b>{users}</b>\n"
    text += f"• Jami guruhlar: <b>{groups}</b>\n"
    text += f"• Aniqlangan xavfli holatlar: <b>{threats}</b>\n\n"

    if daily_stats:
        text += "<b>Oxirgi 7 kunlik statistika:</b>\n"
        for day in daily_stats[:7]:
            text += f"  {day['date']}: Jami {day['total_messages']}, Xavfli {day['threat_messages']}\n"

    if recent_threats:
        text += "\n<b>Oxirgi xavfli xabarlar (5 ta):</b>\n"
        for threat in recent_threats[:5]:
            text += f"• {threat['created_at']} | {threat['threat_level']} | @{threat['username'] or 'noma\'lum'} → {threat['message_text'][:50]}...\n"

    return text


def is_admin(user_id: int) -> bool:
    """
    Foydalanuvchi admin ekanligini tekshirish.
    """
    return user_id in config.ADMIN_IDS


def send_alert_to_admin(bot, message: str) -> None:
    """
    Barcha adminlarga xabar yuborish (masalan, xavfli holat yoki xato).
    """
    for admin_id in config.ADMIN_IDS:
        try:
            bot.send_message(admin_id, f"🚨 ALERT: {message}")
        except Exception as e:
            logger.error(f"Admin {admin_id} ga xabar yuborib bo'lmadi: {e}")


def get_current_timestamp() -> str:
    """
    Hozirgi vaqtni formatlangan holda qaytarish.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_log(message: str, level: str = "info") -> None:
    """
    Xavfsiz loglash: logger bo'lmasa ham ishlaydi.
    """
    if level == "error":
        logger.error(message)
    elif level == "warning":
        logger.warning(message)
    else:
        logger.info(message)