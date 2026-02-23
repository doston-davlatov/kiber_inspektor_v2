import asyncio
import hashlib
import logging
import re
import time
from typing import Dict, Any, Optional
import aiohttp
from aiohttp import ClientTimeout
from virustotal_python import Virustotal
from config import config

logger = logging.getLogger(__name__)

# VirusTotal v3 klientini faqat kalit mavjud bo'lsa ishga tushiramiz
vt = None
if config.VIRUSTOTAL_API_KEY:
    try:
        vt = Virustotal(API_KEY=config.VIRUSTOTAL_API_KEY, API_VERSION="v3")
        logger.info("VirusTotal v3 klient muvaffaqiyatli ishga tushdi")
    except Exception as e:
        logger.error(f"VT klient yaratishda xato: {e}")
        vt = None


async def scan_url(url: str, timeout: int = 35) -> Dict[str, Any]:
    """
    URL ni chuqur va ishonchli tekshirish:
    1. VirusTotal v3 API orqali skan (hash yoki yangi yuklash)
    2. SSL sertifikat va redirect tekshiruvi
    3. Phishing va shubhali patternlar tahlili
    4. Domen yoshi va boshqa ko'rsatkichlar (agar VT dan kelsa)
    """
    # URL ni tozalash va normalizatsiya qilish
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    result: Dict[str, Any] = {
        "url": url,
        "threat": "Unknown",
        "score": 0.0,                # 0-100% xavf darajasi
        "category": "Uncategorized",
        "malicious": 0,
        "suspicious": 0,
        "harmless": 0,
        "undetected": 0,
        "detection_ratio": "0/0",
        "ssl_valid": False,
        "has_redirects": False,
        "redirect_count": 0,
        "phishing_indicators": 0,
        "final_url": url,
        "scan_time": int(time.time()),
        "reason": "",
        "vt_link": f"https://www.virustotal.com/gui/url/{hashlib.sha256(url.encode()).hexdigest()}/detection"
    }

    # Agar VT kaliti yo'q bo'lsa — faqat lokal tekshiruv
    if not vt:
        result["reason"] = "VirusTotal API kaliti sozlanmagan. Faqat lokal tekshiruv bajarildi."
        result["threat"] = "Pending"
        # Lokal tekshiruvni davom ettiramiz
    else:
        try:
            # 1. URL hash orqali qidirish (eng tez)
            url_id = hashlib.sha256(url.encode()).hexdigest()
            try:
                resp = vt.request(f"urls/{url_id}")
                if resp.status_code == 200:
                    data = resp.json()["data"]
                    attrs = data["attributes"]
                    stats = attrs["last_analysis_stats"]

                    result.update({
                        "malicious": stats.get("malicious", 0),
                        "suspicious": stats.get("suspicious", 0),
                        "harmless": stats.get("harmless", 0),
                        "undetected": stats.get("undetected", 0),
                        "detection_ratio": f"{result['malicious'] + result['suspicious']}/{sum(stats.values())}",
                        "category": attrs.get("categories", {}).get("urlhaus", "Uncategorized"),
                        "scan_time": attrs.get("last_analysis_date", result["scan_time"])
                    })

                    # Score hisoblash
                    total = sum(stats.values())
                    if total > 0:
                        result["score"] = round(((result["malicious"] * 3 + result["suspicious"]) / total) * 100, 2)

            except Exception as lookup_err:
                if "404" in str(lookup_err):
                    logger.info(f"URL VT bazasida yo'q, yangi skan boshlanmoqda: {url}")
                else:
                    logger.warning(f"VT lookup xatosi: {lookup_err}")

            # 2. Agar topilmasa yoki yangi skan kerak bo'lsa — URL ni skan qilish
            if result["malicious"] == 0 and result["suspicious"] == 0:
                try:
                    # URL ni VirusTotal ga yuborish
                    submit_resp = vt.request("urls", data={"url": url}, method="POST")
                    if submit_resp.status_code in (200, 201):
                        analysis_id = submit_resp.json()["data"]["id"]

                        # Natijani polling orqali kutish (bepul API uchun 6-10 soniya interval)
                        for attempt in range(20):  # maks ~2 daqiqa
                            await asyncio.sleep(8)
                            report = vt.request(f"analyses/{analysis_id}")
                            if report.status_code == 200:
                                attrs = report.json()["data"]["attributes"]
                                stats = attrs["stats"]

                                result.update({
                                    "malicious": stats.get("malicious", 0),
                                    "suspicious": stats.get("suspicious", 0),
                                    "harmless": stats.get("harmless", 0),
                                    "undetected": stats.get("undetected", 0),
                                    "detection_ratio": f"{result['malicious'] + result['suspicious']}/{sum(stats.values())}",
                                })

                                total = sum(stats.values())
                                if total > 0:
                                    result["score"] = round(((result["malicious"] * 3 + result["suspicious"]) / total) * 100, 2)
                                break
                except Exception as submit_err:
                    logger.error(f"URL skan yuklash xatosi: {submit_err}")

        except Exception as vt_err:
            logger.error(f"VT umumiy xatosi: {vt_err}", exc_info=True)
            result["reason"] += f" VT xatosi: {str(vt_err)[:100]}... | "

    # 3. Lokal tekshiruvlar (VT ishlamasa ham bajariladi)
    try:
        timeout = ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, allow_redirects=True, ssl=False) as resp:
                result["final_url"] = str(resp.url)
                result["ssl_valid"] = resp.url.scheme == "https"
                result["has_redirects"] = len(resp.history) > 0
                result["redirect_count"] = len(resp.history)

    except aiohttp.ClientError as http_err:
        result["reason"] += f"HTTP xatosi: {http_err} | "
        result["ssl_valid"] = False

    # 4. Phishing va shubhali patternlar chuqur tahlili
    phishing_score = 0
    phishing_patterns = [
        r'(login|signin|verify|account|update|secure|bank|paypal|appleid|office|microsoft|amazon)',
        r'(free|bonus|prize|gift|claim|win|money|cash|urgent|immediately)',
        r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})',  # IP domen
        r'(bit\.ly|goo\.gl|t\.co|tinyurl)',        # qisqa linklar
        r'[@#\$%\^&\*]',                           # g'alati belgilar
    ]

    url_lower = url.lower()
    for pattern in phishing_patterns:
        if re.search(pattern, url_lower):
            phishing_score += 1

    # 5. Yakuniy xavf darajasi hisoblash
    total_indicators = result["malicious"] + result["suspicious"] + phishing_score

    if result["malicious"] > 0 or total_indicators >= 5:
        result["threat"] = "High"
        result["score"] = min(95.0, result["score"] + 40 + phishing_score * 8)
    elif result["malicious"] > 0 or phishing_score >= 2 or result["suspicious"] > 0:
        result["threat"] = "Medium"
        result["score"] = min(70.0, result["score"] + 20 + phishing_score * 5)
    elif phishing_score >= 1 or result["has_redirects"]:
        result["threat"] = "Low"
        result["score"] = min(35.0, result["score"] + 10 + phishing_score * 3)
    else:
        result["threat"] = "Safe"
        result["score"] = max(0.0, result["score"] - phishing_score * 2)

    # Yakuniy sabab matni
    reasons = []
    if result["malicious"]:
        reasons.append(f"VT malicious: {result['malicious']}")
    if result["suspicious"]:
        reasons.append(f"suspicious: {result['suspicious']}")
    if phishing_score:
        reasons.append(f"phishing belgilari: {phishing_score}")
    if not result["ssl_valid"]:
        reasons.append("SSL yo'q yoki xato")
    if result["has_redirects"]:
        reasons.append(f"redirect: {result['redirect_count']}")
    if not reasons:
        reasons.append("hech qanday xavf aniqlanmadi")

    result["reason"] = ", ".join(reasons).capitalize() + "."

    return result