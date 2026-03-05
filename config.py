# config.py
import os
import logging
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv, find_dotenv

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

env_path = find_dotenv(usecwd=True)
if env_path:
    load_dotenv(env_path)
    logger.info(f".env yuklandi: {env_path}")

class Config:
    BOT_TOKEN: str
    MYSQL_HOST: str
    MYSQL_PORT: int
    MYSQL_USER: Optional[str] = None
    MYSQL_PASSWORD: Optional[str] = None
    MYSQL_DB: str
    VIRUSTOTAL_API_KEY: str
    
    ADMIN_IDS: List[int] = []
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_SECRET: Optional[str] = None

    MAX_FILE_SIZE: int = 50 * 1024 * 1024
    AI_THRESHOLD: float = 0.70
    RATE_LIMIT: int = 10
    LOG_LEVEL: str = "INFO"

    TEMP_DIR: Path
    MODEL_PATH: Path

    def __init__(self):
        self.BOT_TOKEN = self._get_required("BOT_TOKEN")

        self.MYSQL_HOST = self._get_required("MYSQL_HOST")
        self.MYSQL_PORT = self._get_int("MYSQL_PORT", 3306)
        self.MYSQL_USER = os.getenv("MYSQL_USER")
        self.MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
        self.MYSQL_DB = self._get_required("MYSQL_DB")

        self.VIRUSTOTAL_API_KEY = self._get_required("VIRUSTOTAL_API_KEY")
        self.GROQ_API_KEY = self._get_required("GROQ_API_KEY")
        self.LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        self.LLM_THRESHOLD = self._get_float("LLM_THRESHOLD", 0.72)
        self.USE_HYBRID = os.getenv("USE_HYBRID", "true").lower() == "true"
        self.OCR_ENABLED = os.getenv("OCR_ENABLED", "true").lower() == "true"
        
        admin_str = os.getenv("ADMIN_IDS", "").strip()
        if admin_str:
            try:
                self.ADMIN_IDS = [int(x.strip()) for x in admin_str.split(",") if x.strip().isdigit()]
            except ValueError as e:
                raise ValueError(f"ADMIN_IDS noto'g'ri: {admin_str} → {e}")

        self.MAX_FILE_SIZE = self._get_int("MAX_FILE_SIZE", 50_000_000)
        self.AI_THRESHOLD = self._get_float("AI_THRESHOLD", 0.7)
        self.RATE_LIMIT = self._get_int("RATE_LIMIT", 10)

        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
        if self.LOG_LEVEL not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            self.LOG_LEVEL = "INFO"

        temp_dir_str = os.getenv("TEMP_DIR", "temp").rstrip("/")
        self.TEMP_DIR = Path(temp_dir_str)
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)

        model_path_str = os.getenv("MODEL_PATH", "models/scam_model.pkl")
        self.MODEL_PATH = Path(model_path_str)

        self.WEBHOOK_URL = None
        self.WEBHOOK_SECRET = None

        self._validate()

    def _get_required(self, key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise ValueError(f"{key} topilmadi!")
        return value

    def _get_int(self, key: str, default: int) -> int:
        val = os.getenv(key)
        if val is None:
            return default
        try:
            return int(val)
        except:
            raise ValueError(f"{key} integer bo'lishi kerak")

    def _get_float(self, key: str, default: float) -> float:
        val = os.getenv(key)
        if val is None:
            return default
        try:
            return float(val)
        except:
            raise ValueError(f"{key} float bo'lishi kerak")

    def _validate(self):
        if not (1 <= self.MYSQL_PORT <= 65535):
            raise ValueError(f"MYSQL_PORT noto'g'ri: {self.MYSQL_PORT}")

        if not 0.0 <= self.AI_THRESHOLD <= 1.0:
            raise ValueError(f"AI_THRESHOLD [0–1] oralig'ida bo'lishi kerak")

config = Config()