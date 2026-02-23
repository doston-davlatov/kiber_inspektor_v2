import os
import logging
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv, find_dotenv

# Lokalda .env fayli mavjud bo'lsa uni yuklaymiz
env_path = find_dotenv(usecwd=True)
if env_path:
    load_dotenv(env_path)
    print(f".env fayli yuklandi: {env_path}")
else:
    print("Lokal .env topilmadi → faqat system environment variables ishlatiladi")

class Config:
    """Bot konfiguratsiyasi: .env yoki environment variables dan o'qiladi."""

    BOT_TOKEN: str
    MYSQL_HOST: str
    MYSQL_PORT: int
    MYSQL_USER: Optional[str] = None
    MYSQL_PASSWORD: Optional[str] = None          # ← endi ixtiyoriy
    MYSQL_DB: str
    VIRUSTOTAL_API_KEY: str

    ADMIN_IDS: List[int] = []
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_SECRET: Optional[str] = None

    MAX_FILE_SIZE: int = 50 * 1024 * 1024          # 50 MB
    AI_THRESHOLD: float = 0.70
    RATE_LIMIT: int = 10                           # so'rov/min
    LOG_LEVEL: str = "INFO"

    TEMP_DIR: Path
    MODEL_PATH: Path

    def __init__(self):
        self.BOT_TOKEN = self._get_required("BOT_TOKEN")

        self.MYSQL_HOST     = os.getenv("MYSQL_HOST")
        self.MYSQL_PORT     = self._get_int("MYSQL_PORT")
        self.MYSQL_USER     = os.getenv("MYSQL_USER")           # ixtiyoriy, None bo'lishi mumkin
        self.MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")       # ← endi majburiy emas, None bo'lishi mumkin
        self.MYSQL_DB       = self._get_required("MYSQL_DB")

        self.VIRUSTOTAL_API_KEY = self._get_required("VIRUSTOTAL_API_KEY")

        # Adminlar ro'yxati
        admin_str = os.getenv("ADMIN_IDS", "").strip()
        if admin_str:
            try:
                self.ADMIN_IDS = [
                    int(x.strip()) for x in admin_str.split(",")
                    if x.strip().isdigit()
                ]
            except ValueError as e:
                raise ValueError(f"ADMIN_IDS noto'g'ri: {admin_str} → {e}")

        # Qo'shimcha sozlamalar
        self.MAX_FILE_SIZE  = self._get_int("MAX_FILE_SIZE",  50_000_000)
        self.AI_THRESHOLD   = self._get_float("AI_THRESHOLD", 0.7)
        self.RATE_LIMIT     = self._get_int("RATE_LIMIT",     10)

        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
        if self.LOG_LEVEL not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            self.LOG_LEVEL = "INFO"

        # Papkalar va fayllar
        temp_dir_str = os.getenv("TEMP_DIR", "temp").rstrip("/")
        self.TEMP_DIR = Path(temp_dir_str)
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)

        model_path_str = os.getenv("MODEL_PATH", "models/scam_model.pkl")
        self.MODEL_PATH = Path(model_path_str)

        # Webhook
        webhook_url = os.getenv("WEBHOOK_URL", "").strip()
        if webhook_url:
            self.WEBHOOK_URL = webhook_url.rstrip("/") + "/"
        
        self.WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

        self._validate()

    def _get_required(self, key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise ValueError(f"{key} muhim o'zgaruvchi .env yoki environmentda topilmadi!")
        return value

    def _get_int(self, key: str, default: int) -> int:
        val = os.getenv(key)
        if val is None:
            return default
        try:
            return int(val)
        except (ValueError, TypeError):
            raise ValueError(f"{key} integer bo'lishi kerak (hozirgi qiymat: {val})")

    def _get_float(self, key: str, default: float) -> float:
        val = os.getenv(key)
        if val is None:
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            raise ValueError(f"{key} float bo'lishi kerak (hozirgi qiymat: {val})")

    def _validate(self):
        if not (1 <= self.MYSQL_PORT <= 65535):
            raise ValueError(f"MYSQL_PORT noto'g'ri: {self.MYSQL_PORT}")

        if self.MAX_FILE_SIZE < 1_000_000:
            raise ValueError("MAX_FILE_SIZE juda kichik (kamida 1MB tavsiya etiladi)")

        if not 0.0 <= self.AI_THRESHOLD <= 1.0:
            raise ValueError(f"AI_THRESHOLD [0.0 .. 1.0] oralig'ida bo'lishi kerak, hozir: {self.AI_THRESHOLD}")

        # Parol ixtiyoriy bo'lgani uchun qo'shimcha tekshiruv shart emas

    def __repr__(self):
        sensitive = {"BOT_TOKEN", "MYSQL_PASSWORD", "VIRUSTOTAL_API_KEY", "WEBHOOK_SECRET"}
        attrs = {}
        for k, v in self.__dict__.items():
            if k in sensitive and v is not None:
                attrs[k] = "****"
            else:
                attrs[k] = v
        return f"Config({', '.join(f'{k}={v!r}' for k, v in attrs.items())})"


# Global instance
config = Config()