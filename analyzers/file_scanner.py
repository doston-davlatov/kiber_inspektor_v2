import asyncio
import hashlib
import logging
import os
from typing import Dict, Any
from virustotal_python import Virustotal
from config import config

logger = logging.getLogger(__name__)

# v3 API interfeysini ishga tushiramiz
vt = Virustotal(API_KEY=config.VIRUSTOTAL_API_KEY, API_VERSION="v3") if config.VIRUSTOTAL_API_KEY else None

def calculate_file_hash(file_path: str) -> str:
    """Faylning SHA256 hashini hisoblash."""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        logger.error(f"Hash hisoblashda xato: {e}")
        return ""

async def scan_file(file_path: str) -> Dict[str, Any]:
    """
    Faylni VirusTotal v3 API orqali tekshirish.
    Hash orqali qidiradi, topilmasa upload qiladi.
    """
    if not os.path.exists(file_path):
        return {"threat": "Unknown", "positives": 0, "total": 0, "reason": "Fayl topilmadi"}

    result = {
        "threat": "Safe",
        "positives": 0,
        "total": 0,
        "sha256": calculate_file_hash(file_path),
        "reason": ""
    }

    if not vt:
        result["reason"] = "VirusTotal API kaliti sozlanmagan"
        return result

    try:
        # 1. Avval hash orqali bazadan qidirib ko'ramiz (juda tez)
        try:
            resp = vt.get_object(f"/files/{result['sha256']}")
            stats = resp.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            
            result["positives"] = stats.get("malicious", 0)
            result["total"] = sum(stats.values())
            
        except Exception as e:
            # 2. Agar bazada topilmasa (404), faylni yuklaymiz (upload)
            if "404" in str(e):
                logger.info(f"Fayl bazada yo'q, yuklanmoqda: {file_path}")
                with open(file_path, "rb") as f:
                    files = {"file": (os.path.basename(file_path), f)}
                    upload_resp = vt.request("files", method="POST", files=files)
                
                # Yuklangandan keyin tahlil tayyor bo'lishi uchun kutish (bepul API uchun)
                result["reason"] = "Fayl yangi, tahlil navbatga qo'yildi."
                return result
            else:
                raise e

        # 3. Yakuniy baholash
        if result["positives"] > 2:
            result["threat"] = "High"
        elif result["positives"] > 0:
            result["threat"] = "Low"
        
        result["reason"] = f"VT: {result['positives']}/{result['total']} xavf aniqladi."

    except Exception as e:
        logger.error(f"VT Scan xatosi: {e}")
        result["threat"] = "Unknown"
        result["reason"] = f"API xatosi: {str(e)}"

    finally:
        # Temp faylni o'chirish (Kiber-inspektor botining asosiy logikasi uchun)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Temp fayl o'chirildi: {file_path}")
            except Exception as e:
                logger.warning(f"Faylni o'chirishda xato: {e}")

    return result

# Test qismi
if __name__ == "__main__":
    async def test():
        test_path = "test_virus_sample.txt"
        with open(test_path, "w") as f:
            f.write("X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*")
        
        print("Skanerlash boshlandi...")
        res = await scan_file(test_path)
        print(f"Natija: {res}")

    asyncio.run(test())