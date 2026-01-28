# analyzers/text_analyzer.py
"""
Matn tahlili: scam/phishing aniqlash uchun ML va qoida asosidagi tizim.
"""

import re
import logging
import os
from typing import Dict, Any
import joblib
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from config import config

# NLTK ma'lumotlarini yuklash (bir marta)
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)

logger = logging.getLogger(__name__)

# Uzbek + English + Russian stop words (ko'proq tilli qilish uchun)
STOP_WORDS = set(stopwords.words('english') + stopwords.words('russian'))
# Uzbek stop words qo'lda qo'shilgan (chunki NLTK da to'liq emas)
UZBEK_STOP = {
    'va', 'bilan', 'da', 'dan', 'ga', 'ni', 'ning', 'lar', 'da', 'de', 'bu', 'shu',
    'u', 'o', 'men', 'sen', 'biz', 'siz', 'ular', 'bu', 'shu', 'o', 'qilmoq', 'bo\'lmoq'
}
STOP_WORDS.update(UZBEK_STOP)

# Model va vectorizer yo'llari
MODEL_PATH = config.MODEL_PATH
VECTORIZER_PATH = os.path.join(os.path.dirname(MODEL_PATH), "vectorizer.pkl")

# Global o'zgaruvchilar (lazy loading)
_model = None
_vectorizer = None
_pipeline = None

def load_model():
    """Model va vectorizerni yuklash (lazy)."""
    global _model, _vectorizer, _pipeline
    if _pipeline is not None:
        return

    try:
        if os.path.exists(MODEL_PATH) and os.path.exists(VECTORIZER_PATH):
            _model = joblib.load(MODEL_PATH)
            _vectorizer = joblib.load(VECTORIZER_PATH)
            _pipeline = Pipeline([
                ('tfidf', _vectorizer),
                ('clf', _model)
            ])
            logger.info("✅ Scam model yuklandi")
        else:
            logger.warning("Model fayllari topilmadi. Avval train_scam_model() chaqiring.")
    except Exception as e:
        logger.error(f"Model yuklashda xato: {e}")
        raise


def train_scam_model(save: bool = True) -> None:
    """
    Oddiy modelni train qilish (real loyihada kattaroq dataset bilan ishlatiladi).
    Bu misol uchun – haqiqiy dataset (Kaggle SMS Spam yoki o'zbek scam matnlari) bilan almashtiring.
    """
    global _pipeline

    # Misol dataset (realda 1000+ misol bo'lishi kerak)
    texts = [
        "Siz 10 million so'm yutdingiz! Linkni bosing: https://fake.com",
        "Bankdan xabar: Kartangiz bloklandi, parolni yangilang!",
        "Tez pul topish usuli – hozir bosing!",
        "Salom do'stim, bugun nima qilyapsan?",
        "Assalomu alaykum, yaxshimisiz?",
        "Sizga sovg'a yubormoqchiman, raqamingizni yozing",
        "Telegram premium bepul – faqat bugun!",
    ]
    labels = [1, 1, 1, 0, 0, 1, 1]  # 1 = scam, 0 = safe

    try:
        vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words=list(STOP_WORDS),
            ngram_range=(1, 2),
            lowercase=True
        )
        clf = LogisticRegression(max_iter=1000, class_weight='balanced')
        pipeline = Pipeline([('tfidf', vectorizer), ('clf', clf)])
        pipeline.fit(texts, labels)

        if save:
            os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
            joblib.dump(pipeline.named_steps['clf'], MODEL_PATH)
            joblib.dump(pipeline.named_steps['tfidf'], VECTORIZER_PATH)
            logger.info(f"✅ Model saqlandi: {MODEL_PATH}")

        _pipeline = pipeline
        logger.info("Model train qilindi va yuklandi")
    except Exception as e:
        logger.error(f"Train jarayonida xato: {e}")
        raise


def preprocess_text(text: str) -> str:
    """Matnni tozalash va tayyorlash."""
    text = text.lower()
    # URL larni olib tashlash
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    # Maxsus belgilarni tozalash
    text = re.sub(r'[^\w\s]', '', text)
    # Tokenlash va stop words olib tashlash
    tokens = word_tokenize(text)
    tokens = [word for word in tokens if word not in STOP_WORDS and len(word) > 2]
    return ' '.join(tokens)


def analyze_text(text: str, threshold: float = None) -> Dict[str, Any]:
    """
    Matnni tahlil qilish va scam ehtimolini qaytarish.
    Natija: {'threat': 'Safe'/'Low'/'High', 'score': 0.0-1.0, 'reason': '...'}
    """
    if not text or len(text.strip()) < 5:
        return {"threat": "Safe", "score": 0.0, "reason": "Matn juda qisqa"}

    threshold = threshold or config.AI_THRESHOLD

    load_model()  # Modelni yuklash

    try:
        cleaned_text = preprocess_text(text)

        if _pipeline is None:
            # Model yo'q bo'lsa faqat qoida asosida ishlaymiz
            logger.warning("ML model topilmadi, faqat qoida asosida ishlayapman")
            return rule_based_analysis(text)

        # ML predict
        prob = _pipeline.predict_proba([cleaned_text])[0]
        score = prob[1]  # scam sinfi ehtimoli

        # Qo'shimcha qoida kuchaytirgich
        scam_keywords = [
            'yutuq', 'yutdingiz', 'pul oling', 'parol', 'kartangiz', 'bloklandi',
            'tez pul', 'sovg‘a', 'premium bepul', 'linkni bosing', 'hisobingiz'
        ]
        rule_score = sum(1 for kw in scam_keywords if kw in text.lower()) / len(scam_keywords)
        final_score = (score * 0.7) + (rule_score * 0.3)  # ML ga ko'proq vazn

        if final_score > threshold:
            threat = "High"
        elif final_score > threshold * 0.4:
            threat = "Low"
        else:
            threat = "Safe"

        reason = f"ML score: {score:.3f}, Qoida score: {rule_score:.3f}"
        return {"threat": threat, "score": final_score, "reason": reason}

    except Exception as e:
        logger.error(f"Text analyze xatosi: {e}")
        return {"threat": "Unknown", "score": 0.0, "reason": str(e)}


def rule_based_analysis(text: str) -> Dict[str, Any]:
    """Model bo'lmaganda ishlaydigan oddiy qoida asosidagi tahlil."""
    scam_patterns = [
        r'(yutuq|yutdingiz|million|so‘m|dollar) .* (oling|tez|hozir)',
        r'(parol|kartangiz|hisob) .* (o‘zgartiring|bloklandi)',
        r'(sovg‘a|premium|hisob) .* (bepul|hozir)',
        r'https?://.*(claim|bonus|prize)',
    ]

    score = 0
    for pattern in scam_patterns:
        if re.search(pattern, text.lower(), re.IGNORECASE):
            score += 0.35

    score = min(score, 1.0)
    threat = "High" if score > 0.7 else "Low" if score > 0.3 else "Safe"
    return {"threat": threat, "score": score, "reason": "Qoida asosida tahlil"}


# Bir marta train qilish uchun (faqat kerak bo'lganda chaqiriladi)
# train_scam_model()