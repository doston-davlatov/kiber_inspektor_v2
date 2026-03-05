import logging
import re
import joblib
import nltk
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from pathlib import Path
from groq import Groq, GroqError
from config import config
from typing import Dict, Optional

logger = logging.getLogger(__name__)

nltk_ready = False
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
    nltk_ready = True
except LookupError:
    pass

STOP_WORDS = set()
if nltk_ready:
    try:
        STOP_WORDS = set(stopwords.words('english')) | set(stopwords.words('russian')) | \
                     {'pul', 'so‘m', 'kartangiz', 'bloklandi', 'yutuq', 'tezkor', 'xavfsiz', 'ishonchli'}
    except:
        pass

MODEL_PATH = config.MODEL_PATH
VECTORIZER_PATH = MODEL_PATH.parent / "vectorizer.pkl"

ml_model = None
vectorizer = None

if MODEL_PATH.exists():
    try:
        ml_model = joblib.load(MODEL_PATH)
        vectorizer = joblib.load(VECTORIZER_PATH)
        logger.info("ML model yuklandi")
    except Exception as e:
        logger.warning(f"ML model yuklanmadi: {e}")

groq_client = None
if config.GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=config.GROQ_API_KEY)
        logger.info("Groq klient ishga tushdi")
    except Exception as e:
        logger.error(f"Groq ulanish xatosi: {e}")

async def preprocess_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'http\S+|www\S+|@\S+|#[^\s]+', '', text.lower())
    text = re.sub(r'[^\w\s]', '', text)
    tokens = nltk.word_tokenize(text) if nltk_ready else text.split()
    tokens = [t for t in tokens if t not in STOP_WORDS and len(t) > 2]
    return ' '.join(tokens)

def ml_predict(text: str) -> Dict:
    if not ml_model or not vectorizer:
        return {"threat": "Unknown", "score": 0.0, "reason": "ML model mavjud emas"}

    cleaned = preprocess_text(text)
    if not cleaned:
        return {"threat": "Safe", "score": 0.0, "reason": "Matn bo'sh"}

    vec = vectorizer.transform([cleaned])
    prob = ml_model.predict_proba(vec)[0]
    score = prob[1] if len(prob) > 1 else prob[0]
    label = "High" if score >= config.AI_THRESHOLD else "Low" if score >= 0.4 else "Safe"
    return {"threat": label, "score": float(score), "reason": f"ML score: {score:.3f}"}

async def llm_analyze(text: str) -> Dict:
    if not groq_client:
        return {"threat": "Unknown", "score": 0.0, "reason": "Groq API yo'q"}

    prompt = f"""Sen professional kiberjinoyat detektorisiz. Quyidagi matnni tahlil qiling:
- Phishing, scam, moliyaviy firibgarlik, zararli havola yoki faylni aniqlang
- O'zbek, rus, ingliz tillarida yozilgan bo'lishi mumkin
- Javobni faqat JSON formatida qaytaring, hech qanday qo'shimcha matn yo'q:
{{
  "threat": "High" yoki "Low" yoki "Safe",
  "score": 0.0 dan 1.0 gacha (ishonch darajasi),
  "reason": "qisqa izoh (o'zbek tilida)"
}}

Matn:
{text[:4000]}"""   # uzun matnlar uchun kesish

    try:
        response = groq_client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300,
            top_p=0.95
        )
        content = response.choices[0].message.content.strip()
        
        import json
        try:
            result = json.loads(content)
            if isinstance(result, dict) and "threat" in result:
                return result
        except:
            pass
        
        return {"threat": "Unknown", "score": 0.0, "reason": f"LLM javobi noto'g'ri: {content[:100]}"}
        
    except GroqError as e:
        logger.error(f"Groq xatosi: {e}")
        return {"threat": "Unknown", "score": 0.0, "reason": str(e)}
    except Exception as e:
        logger.exception("LLM tahlil xatosi")
        return {"threat": "Unknown", "score": 0.0, "reason": "LLM ishlamadi"}

def combine_results(ml: Dict, llm: Dict) -> Dict:
    if not config.USE_HYBRID:
        return llm if groq_client else ml
    
    ml_score = ml.get("score", 0.0)
    llm_score = llm.get("score", 0.0)
    
    hybrid_score = (ml_score * 0.35) + (llm_score * 0.65)
    
    if hybrid_score >= config.LLM_THRESHOLD:
        threat = "High"
    elif hybrid_score >= 0.45:
        threat = "Low"
    else:
        threat = "Safe"
    
    reasons = []
    if ml.get("reason"): reasons.append(ml["reason"])
    if llm.get("reason"): reasons.append(llm["reason"])
    
    return {
        "threat": threat,
        "score": round(hybrid_score, 3),
        "reason": " | ".join(reasons) or "Hybrid tahlil",
        "ml": ml,
        "llm": llm
    }

def train_scam_model():
    """Bu funksiya hozircha ishlatilmayapti yoki yangi dataset bilan qayta o'qitish kerak."""
    logger.warning("train_scam_model chaqirildi, lekin hozir implementatsiya qilinmagan")
    return {"status": "skipped", "message": "Modelni qayta o'qitish funksiyasi vaqtincha o'chirilgan"}

def analyze_text(text: str) -> Dict:
    if not text:
        return {"threat": "Safe", "score": 0.0, "reason": "Matn yo'q"}

    ml_result = ml_predict(text)
    
    if groq_client:
        import asyncio
        llm_result = asyncio.run(llm_analyze(text))
        return combine_results(ml_result, llm_result)
    
    return ml_result