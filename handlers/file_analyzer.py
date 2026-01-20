# file_analyzer.py - To'g'rilangan versiya

import hashlib
import json
import os
import re
import tempfile
import aiohttp
import asyncio
from typing import Dict, List, Optional
import logging
from urllib.parse import urlparse
import mimetypes

logger = logging.getLogger(__name__)

class FixedFileAnalyzer:
    def __init__(self):
        # API kalitlari (ixtiyoriy)
        self.vt_api_key = os.getenv('VIRUSTOTAL_API_KEY', '')
        self.gemini_api_key = os.getenv('GEMINI_API_KEY', '')
        
        # Xavfli patternlar
        self.malicious_patterns = {
            'executables': [b'MZ', b'ELF', b'#!/bin/', b'powershell', b'cmd.exe'],
            'scripts': [b'eval(', b'system(', b'exec(', b'base64_decode'],
            'obfuscated': [b'\x1F\x8B', b'PK\x03\x04', b'Rar!\x1A\x07']
        }
        
        # Fayl turlari bo'yicha risk baholari
        self.risk_scores = {
            'high_risk_ext': ['exe', 'dll', 'scr', 'pif', 'com', 'bat', 'cmd', 'vbs', 'js', 'ps1', 'jar', 'apk'],
            'medium_risk_ext': ['msi', 'dmg', 'deb', 'rpm', 'app', 'py', 'php', 'sh'],
            'suspicious_ext': ['zip', 'rar', '7z', 'tar', 'gz', 'iso', 'img']
        }
        
        # Shubhali so'zlar
        self.suspicious_keywords = [
            'crack', 'keygen', 'serial', 'hack', 'password', 'patch',
            'loader', 'activator', 'torrent', 'warez', 'nulled', 'mod'
        ]
    
    async def analyze_telegram_file(self, bot, message) -> Dict:
        """Faylni tahlil qilish - To'g'rilangan versiya"""
        
        print(f"DEBUG: analyze_telegram_file chaqirildi")
        
        try:
            # Fayl ma'lumotlarini olish
            file_info = await self._get_file_info(message)
            if not file_info:
                return self._create_error_result("Fayl ma'lumotlarini olish mumkin emas")
            
            print(f"DEBUG: File info olingan: {file_info['file_name']}")
            
            # Faylni yuklab olish
            file_path = await self._download_telegram_file(bot, file_info)
            if not file_path:
                return self._create_error_result("Faylni yuklab olish mumkin emas")
            
            print(f"DEBUG: Fayl yuklandi: {file_path}")
            
            try:
                # Asosiy tahlil
                result = await self._perform_analysis(file_path, file_info)
                print(f"DEBUG: Tahlil tugadi, natija: {result.get('verdict')}")
                
                return result
                
            finally:
                # Vaqtinchalik faylni o'chirish
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"DEBUG: Fayl o'chirildi: {file_path}")
                except Exception as e:
                    print(f"DEBUG: Fayl o'chirishda xato: {e}")
                    
        except Exception as e:
            print(f"DEBUG: Umumiy xato: {e}")
            logger.error(f"Fayl tahlilida xato: {e}")
            return self._create_error_result(f"Tahlil xatosi: {str(e)[:100]}")
    
    async def _get_file_info(self, message) -> Optional[Dict]:
        """Telegram fayl ma'lumotlarini olish"""
        try:
            if message.document:
                doc = message.document
                return {
                    'file_id': doc.file_id,
                    'file_name': doc.file_name,
                    'file_size': doc.file_size,
                    'mime_type': doc.mime_type,
                    'type': 'document'
                }
            elif message.photo:
                photo = message.photo[-1]
                return {
                    'file_id': photo.file_id,
                    'file_name': f"photo_{photo.file_id}.jpg",
                    'file_size': photo.file_size,
                    'mime_type': 'image/jpeg',
                    'type': 'photo'
                }
            elif message.video:
                video = message.video
                return {
                    'file_id': video.file_id,
                    'file_name': video.file_name or f"video_{video.file_id}.mp4",
                    'file_size': video.file_size,
                    'mime_type': video.mime_type,
                    'type': 'video'
                }
            elif message.audio:
                audio = message.audio
                return {
                    'file_id': audio.file_id,
                    'file_name': audio.file_name or f"audio_{audio.file_id}.mp3",
                    'file_size': audio.file_size,
                    'mime_type': audio.mime_type,
                    'type': 'audio'
                }
        except Exception as e:
            print(f"DEBUG: File info xatosi: {e}")
            logger.error(f"Fayl ma'lumotlarini olishda xato: {e}")
        
        return None
    
    async def _download_telegram_file(self, bot, file_info: Dict) -> Optional[str]:
        """Telegram faylini to'g'ri yuklab olish"""
        try:
            print(f"DEBUG: Fayl yuklanmoqda: {file_info['file_name']}")
            
            # Vaqtinchalik fayl yo'li
            temp_dir = tempfile.gettempdir()
            safe_filename = re.sub(r'[^\w\-_.]', '_', file_info['file_name'])
            file_path = os.path.join(temp_dir, f"tg_{file_info['file_id']}_{safe_filename}")
            
            print(f"DEBUG: Fayl yo'li: {file_path}")
            
            # Faylni yuklab olish
            file = await bot.get_file(file_info['file_id'])
            
            # To'g'ri download metodini ishlatish
            await bot.download_file(file.file_path, destination=file_path)
            
            print(f"DEBUG: Fayl muvaffaqiyatli yuklandi, hajmi: {os.path.getsize(file_path)} bayt")
            
            return file_path
            
        except Exception as e:
            print(f"DEBUG: Yuklash xatosi: {e}")
            logger.error(f"Faylni yuklab olishda xato: {e}")
            return None
    
    async def _perform_analysis(self, file_path: str, file_info: Dict) -> Dict:
        """Faylni tahlil qilish"""
        
        result = {
            'file_name': file_info['file_name'],
            'file_size': file_info['file_size'],
            'mime_type': file_info['mime_type'],
            'risk_level': 'Safe',
            'score': 0,
            'warnings': [],
            'verdict': 'Safe',
            'details': {},
            'content_findings': [],
            'extension': self._get_extension(file_info['file_name'])
        }
        
        try:
            # 1. Hash hisoblash
            file_hash = self._calculate_hash(file_path)
            result['file_hash'] = file_hash
            result['details']['sha256'] = file_hash
            
            # 2. Fayl kengaytmasi tekshirish
            ext_analysis = self._analyze_extension(result['extension'])
            result['score'] += ext_analysis['score']
            result['warnings'].extend(ext_analysis['warnings'])
            
            # 3. Binary pattern tekshirish
            if os.path.getsize(file_path) < 10 * 1024 * 1024:  # 10MB dan kichik bo'lsa
                patterns = self._scan_binary_patterns(file_path)
                if patterns:
                    result['content_findings'].extend(patterns)
                    result['score'] += len(patterns) * 3
            
            # 4. Text fayl tahlili (agar text bo'lsa)
            if self._is_text_file(file_path):
                text_analysis = await self._analyze_text_content(file_path)
                result['content_findings'].extend(text_analysis.get('findings', []))
                result['score'] += text_analysis.get('score', 0)
            
            # 5. Fayl nomi tekshirish
            name_analysis = self._analyze_filename(file_info['file_name'])
            result['warnings'].extend(name_analysis['warnings'])
            result['score'] += name_analysis['score']
            
            # 6. Fayl hajmi tekshirish
            size_analysis = self._analyze_filesize(file_info['file_size'])
            result['warnings'].extend(size_analysis['warnings'])
            result['score'] += size_analysis['score']
            
            # 7. MIME turi tekshirish
            mime_analysis = self._analyze_mime_type(file_info['mime_type'])
            result['warnings'].extend(mime_analysis['warnings'])
            result['score'] += mime_analysis['score']
            
            # Risk darajasi
            result['risk_level'] = self._calculate_risk_level(result['score'])
            result['verdict'] = self._get_verdict(result['risk_level'])
            
            print(f"DEBUG: Tahlil natijasi - Score: {result['score']}, Verdict: {result['verdict']}")
            
            return result
            
        except Exception as e:
            print(f"DEBUG: Tahlil xatosi: {e}")
            result['warnings'].append(f"Tahlil xatosi: {str(e)[:50]}")
            return result
    
    def _calculate_hash(self, file_path: str) -> str:
        """SHA-256 hash hisoblash"""
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                # Katta fayllar uchun chunk-lar bilan o'qish
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
        except Exception as e:
            print(f"DEBUG: Hash hisoblash xatosi: {e}")
            return "hash_error"
        
        return sha256.hexdigest()
    
    def _analyze_extension(self, extension: str) -> Dict:
        """Fayl kengaytmasini tahlil qilish"""
        score = 0
        warnings = []
        
        ext_lower = extension.lower()
        
        # Yuqori xavfli kengaytmalar
        if ext_lower in self.risk_scores['high_risk_ext']:
            score += 25
            warnings.append(f"Yuqori xavfli fayl turi: .{ext_lower}")
            
            # APK uchun maxsus ogohlantirish
            if ext_lower == 'apk':
                warnings.append("APK fayllari virus yoki zararli dastur bo'lishi mumkin")
        
        # O'rta xavfli kengaytmalar
        elif ext_lower in self.risk_scores['medium_risk_ext']:
            score += 15
            warnings.append(f"O'rta xavfli fayl turi: .{ext_lower}")
        
        # Shubhali kengaytmalar
        elif ext_lower in self.risk_scores['suspicious_ext']:
            score += 10
            warnings.append(f"Shubhali fayl turi: .{ext_lower}")
        
        return {'score': score, 'warnings': warnings}
    
    def _scan_binary_patterns(self, file_path: str) -> List[str]:
        """Binary patternlarni tekshirish"""
        findings = []
        try:
            with open(file_path, 'rb') as f:
                # Faqat birinchi 4KB ni o'qish
                content = f.read(4096)
                
                # Executable patternlar
                if b'MZ' in content:
                    findings.append("Windows executable (MZ header)")
                
                if b'ELF' in content:
                    findings.append("Linux executable (ELF header)")
                
                # Script patternlar
                if b'#!/bin/bash' in content or b'#!/bin/sh' in content:
                    findings.append("Shell script detected")
                
                if b'powershell' in content.lower():
                    findings.append("PowerShell script detected")
                
                # Obfuscation
                if b'\x1F\x8B' in content:
                    findings.append("Gzip compressed data")
                
                if b'PK\x03\x04' in content:
                    findings.append("ZIP archive format")
                
        except Exception as e:
            print(f"DEBUG: Binary scan xatosi: {e}")
        
        return findings
    
    async def _analyze_text_content(self, file_path: str) -> Dict:
        """Text fayl kontentini tahlil qilish"""
        findings = []
        score = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(5000)  # Faqat 5000 belgi
                
                # URL lar qidirish
                urls = re.findall(r'https?://[^\s]+', content)
                if urls:
                    findings.append(f"{len(urls)} ta URL topildi")
                    score += len(urls) * 2
                
                # Email manzillar
                emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', content)
                if emails:
                    findings.append(f"{len(emails)} ta email manzil topildi")
                    score += len(emails)
                
                # JavaScript code
                if '<script>' in content.lower() or 'javascript:' in content.lower():
                    findings.append("JavaScript kodi topildi")
                    score += 10
                
                # Base64 encoded data
                base64_pattern = r'[A-Za-z0-9+/=]{50,}'
                base64_matches = re.findall(base64_pattern, content)
                if base64_matches:
                    findings.append("Base64 encoded ma'lumot topildi")
                    score += 8
            
        except Exception as e:
            print(f"DEBUG: Text analysis xatosi: {e}")
        
        return {'findings': findings, 'score': score}
    
    def _analyze_filename(self, filename: str) -> Dict:
        """Fayl nomini tahlil qilish"""
        score = 0
        warnings = []
        
        filename_lower = filename.lower()
        
        # Shubhali so'zlar
        for keyword in self.suspicious_keywords:
            if keyword in filename_lower:
                score += 8
                warnings.append(f"Fayl nomida shubhali so'z: '{keyword}'")
                break
        
        # Double extension
        if re.search(r'\.[a-z]{3,4}\.[a-z]{3,4}$', filename_lower):
            score += 15
            warnings.append("Double extension aniqlandi (masalan: file.pdf.exe)")
        
        # Hash-like names
        name_without_ext = os.path.splitext(filename)[0]
        if re.match(r'^[0-9a-f]{32,64}$', name_without_ext):
            score += 10
            warnings.append("Fayl nomi hash ga o'xshaydi")
        
        return {'score': score, 'warnings': warnings}
    
    def _analyze_filesize(self, filesize: int) -> Dict:
        """Fayl hajmini tahlil qilish"""
        score = 0
        warnings = []
        
        # Juda kichik fayllar
        if filesize < 1024:  # 1KB dan kichik
            score += 5
            warnings.append("Fayl juda kichik (potentsial xavf)")
        
        # Juda katta fayllar
        if filesize > 100 * 1024 * 1024:  # 100MB dan katta
            score += 8
            warnings.append("Fayl juda katta (potentsial xavf)")
        
        return {'score': score, 'warnings': warnings}
    
    def _analyze_mime_type(self, mime_type: str) -> Dict:
        """MIME turini tahlil qilish"""
        score = 0
        warnings = []
        
        if not mime_type:
            return {'score': score, 'warnings': warnings}
        
        # Xavfli MIME turlari
        dangerous_mimes = [
            'application/x-msdownload',
            'application/x-dosexec',
            'application/x-executable',
            'application/x-ms-shortcut',
            'application/x-shellscript'
        ]
        
        if mime_type in dangerous_mimes:
            score += 20
            warnings.append(f"Xavfli MIME turi: {mime_type}")
        
        # Octet-stream (binary data)
        elif mime_type == 'application/octet-stream':
            score += 10
            warnings.append("Binary fayl (application/octet-stream)")
        
        return {'score': score, 'warnings': warnings}
    
    def _is_text_file(self, file_path: str) -> bool:
        """Fayl text fayl ekanligini aniqlash"""
        try:
            # Magic number orqali aniqlash
            with open(file_path, 'rb') as f:
                sample = f.read(1024)
                
            # Text fayl belgilari
            text_chars = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)) - {0x7f})
            
            # Agar binary ma'lumot bo'lsa
            if bool(sample.translate(None, text_chars)):
                return False
            
            # MIME turi orqali tekshirish
            import mimetypes
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type and mime_type.startswith('text/'):
                return True
                
            return False
            
        except:
            return False
    
    def _get_extension(self, filename: str) -> str:
        """Fayl kengaytmasini olish"""
        if '.' in filename:
            return filename.split('.')[-1].lower()
        return ""
    
    def _calculate_risk_level(self, score: int) -> str:
        """Risk darajasini hisoblash"""
        if score >= 60:
            return "Critical"
        elif score >= 40:
            return "High"
        elif score >= 25:
            return "Medium"
        elif score >= 10:
            return "Low"
        else:
            return "Safe"
    
    def _get_verdict(self, risk_level: str) -> str:
        """Final verdict berish"""
        verdicts = {
            "Critical": "Malicious",
            "High": "Suspicious",
            "Medium": "Caution",
            "Low": "Low Risk",
            "Safe": "Safe"
        }
        return verdicts.get(risk_level, "Unknown")
    
    def _create_error_result(self, error_message: str) -> Dict:
        """Xato natijasi yaratish"""
        return {
            'file_name': 'Unknown',
            'file_size': 0,
            'risk_level': 'Error',
            'score': 0,
            'warnings': [f"❌ {error_message}"],
            'verdict': 'Error',
            'details': {'error': error_message},
            'content_findings': [],
            'extension': ''
        }
    
    def get_file_verdict_message(self, analysis_result: Dict) -> str:
        """Fayl tahlili natijasiga asoslangan xabar tayyorlash"""
        
        verdict = analysis_result.get('verdict', 'Safe')
        file_name = analysis_result.get('file_name', 'Noma\'lum fayl')
        risk_level = analysis_result.get('risk_level', 'Low')
        score = analysis_result.get('score', 0)
        warnings = analysis_result.get('warnings', [])
        findings = analysis_result.get('content_findings', [])
        file_size = analysis_result.get('file_size', 0)
        
        # Verdict uchun format
        if verdict == "Malicious":
            emoji = "🔴"
            title = "XAVFLI FAYL!"
            action = "BU FAYLNI O'CHIRING!"
        elif verdict == "Suspicious":
            emoji = "🟡"
            title = "SHUBHALI FAYL"
            action = "EHTIYOT BO'LING!"
        elif verdict == "Caution":
            emoji = "🟠"
            title = "DIQQAT KERAK"
            action = "TEKSHIRMASDAN OCHMANG!"
        elif verdict == "Error":
            emoji = "⚫"
            title = "TAHLIL XATOSI"
            action = "QAYTA URINIB KO'RING"
        else:
            emoji = "🟢"
            title = "XAVFSIZ"
            action = "XAVFSIZ"
        
        # Xabar qurilishi
        message = f"{emoji} <b>{title}</b>\n\n"
        message += f"📁 <b>Fayl:</b> <code>{file_name}</code>\n"
        
        if file_size > 0:
            message += f"📊 <b>Hajm:</b> {file_size/(1024*1024):.2f} MB\n"
        
        message += f"🛡️ <b>Xavf darajasi:</b> {risk_level}\n"
        message += f"📈 <b>Risk bahosi:</b> {score}/100\n"
        
        # Hash ko'rsatish
        if 'file_hash' in analysis_result and analysis_result['file_hash'] != 'hash_error':
            hash_short = analysis_result['file_hash'][:16] + "..."
            message += f"🔐 <b>Hash:</b> <code>{hash_short}</code>\n"
        
        message += f"\n"
        
        # Ogohlantirishlar
        if warnings:
            message += "⚠️ <b>Ogohlantirishlar:</b>\n"
            for i, warning in enumerate(warnings[:4], 1):
                message += f"{i}. {warning}\n"
            message += "\n"
        
        # Topilmalar
        if findings:
            message += "🔍 <b>Topilmalar:</b>\n"
            for i, finding in enumerate(findings[:3], 1):
                message += f"{i}. {finding}\n"
            message += "\n"
        
        # APK uchun maxsus maslahat
        if '.apk' in file_name.lower():
            message += "📱 <b>APK uchun maslahat:</b>\n"
            message += "• Faqat Google Play Store dan yuklang\n"
            message += "• Noma'lum manbalardan APK yuklamang\n"
            message += "• Yuklashdan oldin izohlarni o'qing\n\n"
        
        # Harakatlar
        message += f"❌ <b>{action}</b>\n\n"
        
        # Qo'shimcha maslahatlar
        if verdict == 'Malicious':
            message += "💡 <i>Bu faylni darhol o'chiring va antivirus bilan tekshiring.</i>"
        elif verdict == 'Suspicious':
            message += "💡 <i>Faylni Sandbox muhitida tekshiring yoki ishonchli antivirus dasturi bilan skanerlang.</i>"
        elif verdict == 'Safe':
            message += "💡 <i>Fayl xavfsiz ko'rinadi, ammo har doim ehtiyot bo'ling.</i>"
        
        return message

# Global obyekt
file_analyzer = FixedFileAnalyzer()