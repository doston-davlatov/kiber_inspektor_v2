import asyncio
import logging
import re
from typing import Dict, Any
import aiohttp
from virustotal_python import Virustotal # VirustotalError olib tashlandi
from config import config

logger = logging.getLogger(__name__)

# VT clientni xavfsiz yaratish
vt_client = None
if hasattr(config, "VIRUSTOTAL_API_KEY") and config.VIRUSTOTAL_API_KEY:
    vt_client = Virustotal(config.VIRUSTOTAL_API_KEY)

async def scan_url(url: str, timeout: int = 30) -> Dict[str, Any]:
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
        # 1. VirusTotal skanlash
        if vt_client:
            async with aiohttp.ClientSession() as session:
                # URL ni yuborish
                async with session.post(
                    "https://www.virustotal.com/api/v3/urls",
                    headers={"x-apikey": config.VIRUSTOTAL_API_KEY},
                    data={"url": url}, # json o'rniga data ishlatish xavfsizroq
                    timeout=timeout
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        analysis_id = data["data"]["id"]
                        
                        # Natija tayyor bo'lishini kutish
                        await asyncio.sleep(5) 

                        async with session.get(
                            f"https://www.virustotal.com/api/v3/analyses/{analysis_id}",
                            headers={"x-apikey": config.VIRUSTOTAL_API_KEY},
                            timeout=timeout
                        ) as report_resp:
                            if report_resp.status == 200:
                                report = await report_resp.json()
                                stats = report["data"]["attributes"]["stats"]
                                result.update({
                                    "malicious": stats.get("malicious", 0),
                                    "suspicious": stats.get("suspicious", 0),
                                    "harmless": stats.get("harmless", 0),
                                    "undetected": stats.get("undetected", 0),
                                })
                                result["score"] = result["malicious"] + result["suspicious"]

        # 2. SSL va Redirect tekshiruvi
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, allow_redirects=True, timeout=10, ssl=False) as resp:
                    result["ssl_valid"] = resp.url.scheme == 'https'
                    result["redirects"] = len(resp.history) > 0
            except:
                result["ssl_valid"] = False

        # 3. Phishing patternlar
        phishing_indicators = 0
        patterns = [r'login', r'signin', r'verify', r'bank', r'secure', r'update']
        for p in patterns:
            if re.search(p, url.lower()):
                phishing_indicators += 1

        # Yakuniy baholash
        if result["malicious"] > 0 or phishing_indicators >= 2:
            result["threat"] = "High"
        elif phishing_indicators > 0:
            result["threat"] = "Low"
        else:
            result["threat"] = "Safe"

        result["reason"] = f"VT: {result['malicious']}, Phish: {phishing_indicators}, SSL: {result['ssl_valid']}"

    except Exception as e:
        logger.error(f"Skanerlashda xato: {e}")
        result["reason"] = f"Xato: {str(e)}"

    return result