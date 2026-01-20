import re

PATTERNS = {
    "scam": [
        r"yutuq yutdingiz", r"sovg['']a beriladi",
        r"aksiya 202[0-9]", r"bepul pul", r"tez pul",
        r"million yutish", r"bepul iPhone", r"boyish siri",
        r"ishonch kodi", r"tasdiqlash kodi", r"karta ma['']lumoti"
    ],
    "phishing": [
        r"parolingizni", r"karta raqam", r"telefon raqam",
        r"pasport raqam", r"shaxsiy ma['']lumot",
        r"telegram kirish", r"hisobni tiklash", r"faollashtirish"
    ],
    "spam": [
        r"daromad 1 oyda", r"ish uyda", r"ishlayman 1000\$",
        r"ish joyi", r"biznes hamkor", r"sarmoya"
    ]
}

def analyze_message(text: str):
    if not text:
        return None, "Safe"
    
    text_lower = text.lower()
    
    # Scam tekshirish
    for pattern in PATTERNS["scam"]:
        if re.search(pattern, text_lower):
            return "Scam xabari", "High"
    
    # URL tekshirish
    urls = re.findall(r'https?://[^\s]+', text_lower)
    for url in urls:
        if any(domain in url for domain in ['.tk', '.ml', '.ga', '.cf', '.gq', '.xyz']):
            return "Phishing havolasi", "Critical"
    
    # Phishing tekshirish
    for pattern in PATTERNS["phishing"]:
        if re.search(pattern, text_lower):
            return "Phishing xabari", "High"
    
    return None, "Safe"

def analyze_message_advanced(text: str):
    if not text:
        return [], "Safe"
    
    text_lower = text.lower()
    threats = []
    
    for threat_type, patterns in PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                if threat_type == "scam":
                    threats.append("Firibgarlik")
                elif threat_type == "phishing":
                    threats.append("Phishing")
                elif threat_type == "spam":
                    threats.append("Spam")
                break
    
    # Shoshilinchlik so'zlari
    if any(word in text_lower for word in ["tez", "shoshiling", "faqat bugun", "chegirma tugashi", "soni cheklangan"]):
        if threats:
            threats.append("Shoshilinchlik")
    
    # Xavf darajasi
    if "Phishing" in threats:
        severity = "Critical"
    elif "Firibgarlik" in threats:
        severity = "High"
    elif "Spam" in threats:
        severity = "Medium"
    elif threats:
        severity = "Low"
    else:
        severity = "Safe"
    
    return list(set(threats[:3])), severity