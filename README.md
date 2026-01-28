# Kiber-Inspektor Bot

Telegram bot – foydalanuvchilarni phishing, scam, malware va boshqa kiber tahdidlardan himoya qilish uchun yaratilgan.

### Imkoniyatlar
- Matn tekshiruvi: scam va phishing xabarlarni aniqlash (ML + qoida asosida)
- URL skanerlash: VirusTotal + SSL/domain tekshiruvi
- Fayl skanerlash: VirusTotal orqali virus/malware aniqlash
- Guruh monitoringi: guruhdagi xabarlarni avtomatik tekshirish va ogohlantirish
- Support tizimi: foydalanuvchi-admin chat
- Admin paneli: statistika, ban/unban, support so‘rovlarini boshqarish
- Rate limiting va xavfsizlik choralar

### Texnologiyalar
- Python 3.10+
- aiogram 3.x (Telegram Bot API)
- aiomysql (async MySQL)
- VirusTotal API
- scikit-learn + NLTK (matn tahlili uchun ML)
- python-dotenv (konfiguratsiya)