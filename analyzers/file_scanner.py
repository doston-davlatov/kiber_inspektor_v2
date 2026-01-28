# analyzers/file_scanner.py
"""
Fayl skanerlash: VirusTotal orqali hash tekshirish va zarur bo'lsa faylni upload qilish.
"""

import asyncio
import hashlib
import logging
import os
from typing import Dict, Any
from virustotal_python import VirusTotalPublicApi, VirustotalError
from config import config

logger = logging.getLogger(__name__)

vt_client = VirusTotalPublicApi(config.VIRUSTOTAL_API_KEY) if config.VIRUSTOTAL_API_KEY else None

def calculate_file_hash(file_path: str, algorithm: str = 'sha256') -> str:
    """Fayl hashini hisoblash."""
    hash_func = hashlib.new(algorithm)
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    except Exception as e:
        logger.error(f"Hash hisoblash xatosi: {e}")
        return ""


async def scan_file(file_path: str, timeout: int = 60) -> Dict[str, Any]:
    """
    Faylni VirusTotal orqali tekshirish.
    Natija: {'threat': 'Safe'/'Low'/'High'/'Unknown', 'positives': int, 'total': int, 'reason': str}
    """
    if not os.path.exists(file_path):
        return {"threat": "Unknown", "positives": 0, "total": 0, "reason": "Fayl topilmadi"}

    result = {
        "threat": "Unknown",
        "positives": 0,
        "total": 0,
        "sha256": "",
        "md5": "",
        "reason": "",
        "scan_id": None
    }

    try:
        # Hash hisoblash
        sha256 = calculate_file_hash(file_path, 'sha256')
        md5 = calculate_file_hash(file_path, 'md5')
        result["sha256"] = sha256
        result["md5"] = md5

        if vt_client:
            # Reportni tekshirish
            try:
                report = vt_client.get_file_report(sha256)
                if report and report.get("response_code") == 1:
                    stats = report["results"]
                    result["positives"] = stats.get("positives", 0)
                    result["total"] = stats.get("total", 0)
                    result["scan_id"] = stats.get("scan_id")
                else:
                    # Fayl VT da yo'q – upload qilish
                    logger.info(f"Fayl VT da topilmadi, upload qilinmoqda: {file_path}")
                    with open(file_path, "rb") as f:
                        upload_resp = vt_client.scan_file(f, filename=os.path.basename(file_path))
                    if upload_resp.get("response_code") == 1:
                        result["scan_id"] = upload_resp["scan_id"]
                        # Kutish va report olish
                        await asyncio.sleep(30)  # VT vaqt talab qiladi
                        report = vt_client.get_file_report(sha256)
                        if report and report.get("response_code") == 1:
                            stats = report["results"]
                            result["positives"] = stats.get("positives", 0)
                            result["total"] = stats.get("total", 0)
            except VirustotalError as ve:
                result["reason"] = f"VT xatosi: {str(ve)}"

        # Yakuniy baho
        positives = result["positives"]
        if positives > 2:
            result["threat"] = "High"
        elif positives > 0:
            result["threat"] = "Low"
        else:
            result["threat"] = "Safe"

        result["reason"] = f"VT positives: {positives}/{result['total']}, SHA256: {sha256[:16]}..."

    except asyncio.TimeoutError:
        result["reason"] = "Timeout – VirusTotal javob bermadi"
    except Exception as e:
        logger.error(f"Fayl scan xatosi: {e}", exc_info=True)
        result["reason"] = f"Xato: {str(e)}"

    # Faylni o'chirish (temp fayllar uchun)
    try:
        os.remove(file_path)
    except:
        pass

    return result


# Test uchun
if __name__ == "__main__":
    async def test():
        # Test fayl yaratish
        test_path = "test_file.txt"
        with open(test_path, "w") as f:
            f.write("This is a test file")
        res = await scan_file(test_path)
        print(res)

    asyncio.run(test())