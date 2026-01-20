# handlers/monitor.py
from collections import defaultdict
from datetime import datetime, timedelta

class RealTimeMonitor:
    def __init__(self):
        self.user_activity = defaultdict(list)
        
    def track_user(self, user_id, message_text, threat_level):
        """Foydalanuvchi faolligini kuzatish"""
        timestamp = datetime.now()
        self.user_activity[user_id].append({
            "timestamp": timestamp,
            "text": message_text,
            "threat": threat_level
        })
        
        # Faqat oxirgi 10 daqiqadagi xabarlarni saqlash
        self.user_activity[user_id] = [
            msg for msg in self.user_activity[user_id]
            if timestamp - msg["timestamp"] < timedelta(minutes=10)
        ]
        
        recent_threats = sum(1 for msg in self.user_activity[user_id] 
                           if msg["threat"] != "Safe")
        
        return recent_threats

monitor = RealTimeMonitor()