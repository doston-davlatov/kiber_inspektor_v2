import os
from typing import List
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path('.env'))

class Config:
    """Bot konfiguratsiyasi: .env faylidan o'qiladi."""
    
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN .env da topilmadi! BotFather orqali oling.")
    
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_USER: str = os.getenv("MYSQL_USER")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD")
    MYSQL_DB: str = os.getenv("MYSQL_DB")
    
    VIRUSTOTAL_API_KEY: str = os.getenv("VIRUSTOTAL_API_KEY")
    
    ADMIN_IDS: List[int] = []
    admin_str = os.getenv("ADMIN_IDS", "")
    if admin_str:
        try:
            ADMIN_IDS = [int(id.strip()) for id in admin_str.split(",") if id.strip()]
        except ValueError:
            raise ValueError("ADMIN_IDS noto'g'ri formatda! Masalan: 123456,789012")
    
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", 50000000))  # 50 MB default
    AI_THRESHOLD: float = float(os.getenv("AI_THRESHOLD", 0.7))
    RATE_LIMIT: int = int(os.getenv("RATE_LIMIT", 10))  # So'rovlar/min
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    TEMP_DIR: str = os.getenv("TEMP_DIR", "temp/")  # Fayllar uchun temp papka
    MODEL_PATH: str = os.getenv("MODEL_PATH", "models/scam_model.pkl")  # ML model yo'li
    
    # Qo'shimcha: Future-proof uchun webhook URL
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", None)  # Deploy uchun
    
    def __init__(self):
        # Validation: Muhim qiymatlar borligini tekshirish
        required = ["BOT_TOKEN", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DB", "VIRUSTOTAL_API_KEY"]
        for key in required:
            if not getattr(self, key, None):
                raise ValueError(f"{key} .env da topilmadi!")

config = Config()