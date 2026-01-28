# analyzers/url_scanner.py
"""
URL skanerlash: VirusTotal va qo'shimcha tekshiruvlar (SSL, domain yoshligi, phishing belgilari).
"""

import asyncio
import logging
import re
import ssl
from typing import Dict, Any, Optional
import aiohttp
from virustotal_python import VirusTotalPublicApi, VirustotalError
from config import config

logger = logging.getLogger(__name__)

vt_client = VirusTotalPublicApi(config.VIRUSTOTAL_API_KEY) if config.VIRUSTOTAL_API_KEY else None

async def scan_url(url: str, timeout: int = 30) -> Dict[str, Any]:
    """
    URL ni tahlil qilish.
    Natija: {'threat': 'Safe'/'Low'/'High'/'Unknown', 'score': int, 'details': {...}, 'reason': str}
    """
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    result = {
        "threat": "Unknown",
        "score": 0,
        "details": {},
        "reason": "",
        "malicious": 0,
        "suspicious": 0,
        "harmless": 0,
        "undetected": 0,
        "ssl_valid": False,
        "redirects": False
    }

    try:
        # 1. VirusTotal skanlash (async)
        if vt_client:
            async with aiohttp.ClientSession() as session:
                # URL ni submit qilish
                resp = await session.post(
                    "https://www.virustotal.com/api/v3/urls",
                    headers={"x-apikey": config.VIRUSTOTAL_API_KEY},
                    json={"url": url},
                    timeout=timeout
                )
                if resp.status != 200:
                    logger.warning(f"VT submit xatosi: {resp.status} - {await resp.text()}")
                else:
                    data = await resp.json()
                    analysis_id = data["data"]["id"]

                    # Natijani kutish (VT odatda 10-60 soniya ichida tayyor bo'ladi)
                    await asyncio.sleep(15)

                    # Report olish
                    report_resp = await session.get(
                        f"https://www.virustotal.com/api/v3/analyses/{analysis_id}",
                        headers={"x-apikey": config.VIRUSTOTAL_API_KEY},
                        timeout=timeout
                    )
                    if report_resp.status == 200:
                        report = await report_resp.json()
                        stats = report["data"]["attributes"]["stats"]
                        result["malicious"] = stats.get("malicious", 0)
                        result["suspicious"] = stats.get("suspicious", 0)
                        result["harmless"] = stats.get("harmless", 0)
                        result["undetected"] = stats.get("undetected", 0)
                        result["score"] = result["malicious"] + result["suspicious"]

        # 2. Qo'shimcha tekshiruvlar (SSL, redirects, shubhali patternlar)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, allow_redirects=True, timeout=timeout, ssl=False) as resp:
                result["ssl_valid"] = resp.connection.transport.get_extra_info('ssl_object') is not None
                result["redirects"] = len(resp.history) > 0

        # 3. Shubhali patternlar (phishing belgilari)
        phishing_indicators = 0
        if re.search(r'(login|signin|account|verify|update|secure|bank|paypal|appleid)\b', url.lower()):
            phishing_indicators += 1
        if re.search(r'\d{3,}', url):  # Ko'p raqamli domenlar
            phishing_indicators += 1
        if len(url.split('.')) > 4:  # Ko'p subdomain
            phishing_indicators += 1

        # Yakuniy baho
        vt_malicious = result["malicious"]
        if vt_malicious > 2 or phishing_indicators >= 2:
            result["threat"] = "High"
        elif vt_malicious > 0 or phishing_indicators > 0:
            result["threat"] = "Low"
        else:
            result["threat"] = "Safe"

        result["reason"] = (
            f"VT malicious: {vt_malicious}, suspicious: {result['suspicious']}, "
            f"phishing indicators: {phishing_indicators}, "
            f"SSL: {'valid' if result['ssl_valid'] else 'invalid'}, "
            f"redirects: {result['redirects']}"
        )

    except asyncio.TimeoutError:
        result["reason"] = "Timeout – server javob bermadi"
    except VirustotalError as ve:
        result["reason"] = f"VirusTotal xatosi: {str(ve)}"
    except Exception as e:
        logger.error(f"URL scan xatosi: {e}", exc_info=True)
        result["reason"] = f"Xato: {str(e)}"

    return result


# Test uchun (terminaldan ishlatish mumkin)
if __name__ == "__main__":
    async def test():
        res = await scan_url("https://example.com")
        print(res)

    asyncio.run(test())