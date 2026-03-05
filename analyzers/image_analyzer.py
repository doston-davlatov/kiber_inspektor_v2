import logging
from pathlib import Path
import easyocr
from PIL import Image
from groq import Groq
from config import config
import asyncio

logger = logging.getLogger(__name__)

reader = None
if config.OCR_ENABLED:
    try:
        reader = easyocr.Reader(['en', 'ru', 'uz'], gpu=False)
        logger.info("EasyOCR yuklandi")
    except Exception as e:
        logger.error(f"EasyOCR yuklanmadi: {e}")

async def ocr_image(image_path: str) -> str:
    if not reader:
        return "[OCR yo'q]"
    
    try:
        result = reader.readtext(image_path, detail=0, paragraph=True)
        return ' '.join(result)
    except Exception as e:
        logger.error(f"OCR xatosi: {e}")
        return "[OCR xatosi]"

async def vision_analyze(image_path: str, ocr_text: str = "") -> Dict:
    if not config.GROQ_API_KEY:
        return {"threat": "Unknown", "reason": "Groq yo'q"}
    
    client = Groq(api_key=config.GROQ_API_KEY)
    
    # Groq vision hali to'liq qo'llab-quvvatlanmasligi mumkin — shuning uchun OCR + text tahlil
    # Agar vision API ochilsa, base64 image yuborish mumkin
    
    prompt = f"""Rasmda ko'rinadigan matn yoki elementlarni tahlil qiling.
OCR natijasi: {ocr_text}

Bu rasm phishing sahifasi, scam reklama yoki zararli QR kod bo'lishi mumkinmi?
Javob JSON:
{{
  "threat": "High"|"Low"|"Safe",
  "score": 0.0-1.0,
  "reason": "izoh"
}}"""

    try:
        resp = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=250
        )
        content = resp.choices[0].message.content.strip()
        import json
        return json.loads(content)
    except Exception as e:
        logger.error(f"Vision/LLM xatosi: {e}")
        return {"threat": "Unknown", "score": 0.0, "reason": str(e)}

async def analyze_image(image_path: Path) -> Dict:
    if not image_path.exists():
        return {"threat": "Safe", "reason": "Fayl topilmadi"}
    
    ocr_text = await ocr_image(str(image_path))
    vision_result = await vision_analyze(str(image_path), ocr_text)
    
    return {
        "threat": vision_result["threat"],
        "score": vision_result["score"],
        "reason": f"OCR: {ocr_text[:150]}... | {vision_result['reason']}",
        "ocr_text": ocr_text
    }