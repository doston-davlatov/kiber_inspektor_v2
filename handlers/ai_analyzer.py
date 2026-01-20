import re
import numpy as np
from typing import Tuple

class SimpleAIAnalyzer:
    def __init__(self):
        # Scam uchun kalit so'zlar
        self.scam_keywords = [
            'yutuq', 'mukofot', "sovg'a", 'bepul pul', 'tez pul',
            'daromad', 'boyish', 'aksiya', 'promo', 'chegirma',
            'million', 'dollar', 'euro', 'rub', 'sum', 'karta',
            'bank', 'hisob', 'kod', 'parol', 'login', 'kirish'
        ]
        
        # Phishing uchun kalit so'zlar
        self.phishing_keywords = [
            'parolingiz', 'karta raqam', 'telefon raqam',
            'pasport', 'shaxsiy', 'ma\'lumot', 'hisob', 'akkaunt',
            'faollashtirish', 'tasdiqlash', 'kiritish', 'yuborish'
        ]
        
        # Spam uchun kalit so'zlar
        self.spam_keywords = [
            'daromad', 'ish joyi', 'biznes', 'hamkor', 'sarmoya',
            'xizmat', 'narx', 'arzon', 'chegirma', 'taksi', 'kelishuv'
        ]
        
        # Bad domains
        self.bad_domains = ['.tk', '.ml', '.ga', '.cf', '.gq', '.xyz']
    
    def _calculate_similarity(self, text: str, keywords: list) -> float:
        """Matn va kalit so'zlar o'rtasidagi o'xshashlikni hisoblash"""
        text_lower = text.lower()
        matches = 0
        
        for keyword in keywords:
            if keyword in text_lower:
                matches += 1
        
        return matches / len(keywords) if keywords else 0
    
    def predict(self, text: str) -> Tuple[bool, float]:
        """Matnni tahlil qilish"""
        text_lower = text.lower()
        
        # 1. Scam ehtimoli
        scam_score = self._calculate_similarity(text_lower, self.scam_keywords)
        
        # 2. Phishing ehtimoli
        phishing_score = self._calculate_similarity(text_lower, self.phishing_keywords)
        
        # 3. Spam ehtimoli
        spam_score = self._calculate_similarity(text_lower, self.spam_keywords)
        
        # 4. Bad domains tekshirish
        url_score = 0
        urls = re.findall(r'https?://[^\s]+', text_lower)
        for url in urls:
            for domain in self.bad_domains:
                if domain in url:
                    url_score += 0.3
                    break
        
        # 5. Shoshilinchlik so'zlari
        urgency_words = ['tez', 'shoshiling', 'faqat bugun', 'chegirma', 'cheklangan']
        urgency_score = sum(1 for word in urgency_words if word in text_lower) * 0.1
        
        # 6. Asosiy so'zlar
        critical_words = ['pul', 'karta', 'parol', 'bank', 'hisob']
        critical_score = sum(1 for word in critical_words if word in text_lower) * 0.15
        
        # Yakuniy ehtimol
        probability = min(1.0, (
            scam_score * 0.3 +
            phishing_score * 0.4 +
            spam_score * 0.1 +
            url_score * 0.5 +
            urgency_score * 0.3 +
            critical_score * 0.4
        ))
        
        # Agar URL bo'lsa, ehtimollikni oshirish
        if urls:
            probability = min(1.0, probability + 0.2)
        
        # Agar uzun matn bo'lsa, ehtimollikni kamaytirish
        if len(text_lower) > 100:
            probability *= 0.8
        
        is_scam = probability > 0.5
        
        return is_scam, round(probability, 2)
    
    def get_detailed_analysis(self, text: str) -> dict:
        """Batafsil tahlil"""
        text_lower = text.lower()
        
        analysis = {
            "text": text[:200] + "..." if len(text) > 200 else text,
            "length": len(text),
            "has_urls": bool(re.findall(r'https?://[^\s]+', text_lower)),
            "scam_keywords_found": [],
            "phishing_keywords_found": [],
            "spam_keywords_found": [],
            "bad_domains_found": [],
            "risk_factors": [],
            "final_probability": 0.0,
            "verdict": "Safe"
        }
        
        # Scam kalit so'zlari
        for keyword in self.scam_keywords:
            if keyword in text_lower:
                analysis["scam_keywords_found"].append(keyword)
        
        # Phishing kalit so'zlari
        for keyword in self.phishing_keywords:
            if keyword in text_lower:
                analysis["phishing_keywords_found"].append(keyword)
        
        # Spam kalit so'zlari
        for keyword in self.spam_keywords:
            if keyword in text_lower:
                analysis["spam_keywords_found"].append(keyword)
        
        # Bad domains
        urls = re.findall(r'https?://[^\s]+', text_lower)
        for url in urls:
            for domain in self.bad_domains:
                if domain in url:
                    analysis["bad_domains_found"].append(domain)
                    break
        
        # Risk omillari
        if analysis["scam_keywords_found"]:
            analysis["risk_factors"].append(f"Scam so'zlari: {len(analysis['scam_keywords_found'])} ta")
        
        if analysis["phishing_keywords_found"]:
            analysis["risk_factors"].append(f"Phishing so'zlari: {len(analysis['phishing_keywords_found'])} ta")
        
        if analysis["bad_domains_found"]:
            analysis["risk_factors"].append(f"Xavfli domenlar: {len(set(analysis['bad_domains_found']))} ta")
        
        if any(word in text_lower for word in ['tez', 'shoshiling', 'faqat bugun']):
            analysis["risk_factors"].append("Shoshilinchlik ifodalari")
        
        # Yakuniy ehtimol va qaror
        is_scam, probability = self.predict(text)
        analysis["final_probability"] = probability
        
        if probability > 0.8:
            analysis["verdict"] = "Critical"
        elif probability > 0.6:
            analysis["verdict"] = "High"
        elif probability > 0.4:
            analysis["verdict"] = "Medium"
        elif probability > 0.2:
            analysis["verdict"] = "Low"
        else:
            analysis["verdict"] = "Safe"
        
        return analysis

# Global obyekt
ai_analyzer = SimpleAIAnalyzer()