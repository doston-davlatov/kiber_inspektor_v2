import asyncio
import hashlib
import logging
import os
from typing import Dict, Any
from virustotal_python import Virustotal
from config import config

logger = logging.getLogger(__name__)

# VirusTotal v3 API obyekti
vt = Virustotal(
    API_KEY=config.VIRUSTOTAL_API_KEY,
    API_VERSION="v3"
) if config.VIRUSTOTAL_API_KEY else None


def calculate_file_hash(file_path: str) -> str:
    """Faylning SHA-256 hashini hisoblash"""
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
    1. Hash bo'yicha qidirish (tez)
    2. Topilmasa → faylni yuklash (upload)
    3. Natijani qaytarish
    """
    if not os.path.exists(file_path):
        return {
            "threat": "Unknown",
            "positives": 0,
            "total": 0,
            "sha256": "",
            "reason": "Fayl topilmadi yoki ochib bo'lmadi"
        }

    result = {
        "threat": "Safe",
        "positives": 0,
        "total": 0,
        "sha256": calculate_file_hash(file_path),
        "reason": "",
        "detection_ratio": "0/0",
        "scan_date": ""
    }

    if not vt:
        result["reason"] = "VirusTotal API kaliti sozlanmagan"
        result["threat"] = "Unknown"
        return result

    try:
        # 1. Hash bo'yicha qidirish (eng tez usul)
        try:
            resp = vt.request(f"files/{result['sha256']}")
            if resp.status_code == 200:
                data = resp.json()["data"]
                stats = data["attributes"]["last_analysis_stats"]
                result["positives"] = stats.get("malicious", 0) + stats.get("suspicious", 0)
                result["total"] = sum(stats.values())
                result["detection_ratio"] = f"{result['positives']}/{result['total']}"
                result["scan_date"] = data["attributes"].get("last_analysis_date", "Noma'lum")

                if result["positives"] > 2:
                    result["threat"] = "High"
                elif result["positives"] > 0:
                    result["threat"] = "Medium"
                else:
                    result["threat"] = "Safe"

                result["reason"] = f"VirusTotal: {result['detection_ratio']} skaner xavf aniqladi"
                return result

        except Exception as search_err:
            # Agar 404 (fayl topilmagan) bo'lsa → yuklashga o'tamiz
            if "404" in str(search_err):
                logger.info(f"Fayl VT bazasida yo'q, yuklanmoqda: {file_path}")
            else:
                raise search_err

        # 2. Faylni VirusTotal ga yuklash (upload)
        with open(file_path, "rb") as f:
            upload_resp = vt.request(
                "files",
                files={"file": (os.path.basename(file_path), f)},
                method="POST"
            )

        if upload_resp.status_code not in (200, 201):
            logger.error(f"Fayl yuklash xatosi: {upload_resp.status_code} - {upload_resp.text}")
            result["reason"] = "Fayl VirusTotal ga yuklanmadi"
            result["threat"] = "Unknown"
            return result

        # Yuklashdan keyin tahlil ID olamiz
        scan_id = upload_resp.json()["data"]["id"]

        # 3. Tahlil natijasini kutish (polling)
        for attempt in range(25):  # maks ~2.5 daqiqa kutish
            await asyncio.sleep(6)  # VirusTotal bepul API uchun tavsiya etilgan interval
            report_resp = vt.request(f"analyses/{scan_id}")

            if report_resp.status_code == 200:
                attrs = report_resp.json()["data"]["attributes"]
                stats = attrs["stats"]

                result["positives"] = stats.get("malicious", 0) + stats.get("suspicious", 0)
                result["total"] = sum(stats.values())
                result["detection_ratio"] = f"{result['positives']}/{result['total']}"
                result["scan_date"] = attrs.get("date", "Noma'lum")

                if result["positives"] > 2:
                    result["threat"] = "High"
                elif result["positives"] > 0:
                    result["threat"] = "Medium"
                else:
                    result["threat"] = "Safe"

                result["reason"] = f"VirusTotal: {result['detection_ratio']} skaner natijasi"
                return result

        # Agar vaqt tugasa
        result["reason"] = "Tahlil natijasi vaqtida kutilmadi (navbatda qolgan)"
        result["threat"] = "Pending"

    except Exception as e:
        logger.error(f"VirusTotal API umumiy xatosi: {e}", exc_info=True)
        result["threat"] = "Unknown"
        result["reason"] = f"API xatosi: {str(e)[:120]}..."

    finally:
        # Temp faylni tozalash (har doim)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Temp fayl o'chirildi: {file_path}")
            except Exception as rm_err:
                logger.warning(f"Fayl o'chirishda xato: {rm_err}")

    return result
