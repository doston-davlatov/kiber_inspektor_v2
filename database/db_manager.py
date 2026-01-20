import sqlite3
import logging
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any

class Database:
    def __init__(self, db_name: str = "kiber_inspektor.db"):
        self.db_name = db_name
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._ensure_tables()
        self.logger = logging.getLogger(__name__)
    
    def _ensure_tables(self) -> None:
        try:
            # Foydalanuvchilar jadvali
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                trust_score INTEGER DEFAULT 100,
                is_admin BOOLEAN DEFAULT 0,
                is_banned BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Guruhlar jadvali
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS groups (
                group_id INTEGER PRIMARY KEY,
                group_name TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Loglar jadvali
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                user_id INTEGER,
                message_text TEXT,
                threat_level TEXT DEFAULT 'Safe',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (group_id) REFERENCES groups (group_id)
            )''')
            
            # Support so'rovlar
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS support_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                status TEXT DEFAULT 'pending',
                subject TEXT,
                last_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )''')
            
            # Support conversation
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS support_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER,
                sender_id INTEGER,
                message_text TEXT,
                is_from_user BOOLEAN,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES support_requests (id)
            )''')
            
            # User states (holatlar)
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state TEXT,
                data TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Messages (user-admin muloqoti)
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                admin_id INTEGER,
                message_text TEXT,
                is_from_user BOOLEAN,
                is_read BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )''')
            
            self.conn.commit()
            print("✅ Ma'lumotlar bazasi jadvallari yaratildi")
            
        except Exception as e:
            print(f"❌ Jadval yaratishda xato: {e}")
    
    def add_user(self, user_id: int, username: Optional[str], full_name: str) -> bool:
        try:
            self.cursor.execute('''INSERT OR IGNORE INTO users 
                                (user_id, username, full_name)
                                VALUES (?, ?, ?)''',
                                (user_id, username, full_name))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ add_user xatosi: {e}")
            return False
    
    def add_group(self, group_id: int, group_name: str) -> bool:
        try:
            self.cursor.execute('''INSERT OR IGNORE INTO groups 
                                (group_id, group_name)
                                VALUES (?, ?)''',
                                (group_id, group_name))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ add_group xatosi: {e}")
            return False
    
    def log_message(self, group_id: Optional[int], user_id: int, 
                    text: str, threat_level: str = "Safe") -> bool:
        try:
            text_short = text[:200] if text else ""
            
            self.cursor.execute('''INSERT INTO logs 
                                (group_id, user_id, message_text, threat_level, created_at)
                                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                                (group_id, user_id, text_short, threat_level))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"❌ log_message xatosi: {e}")
            return False
    
    def create_support_request(self, user_id: int, subject: str, message: str) -> Optional[int]:
        try:
            self.cursor.execute('''INSERT INTO support_requests 
                                (user_id, subject, last_message, status, created_at, updated_at)
                                VALUES (?, ?, ?, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
                                (user_id, subject, message))
            request_id = self.cursor.lastrowid
            
            self.cursor.execute('''INSERT INTO support_conversations 
                                (request_id, sender_id, message_text, is_from_user, created_at)
                                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)''',
                                (request_id, user_id, message))
            
            self.conn.commit()
            return request_id
        except Exception as e:
            print(f"❌ create_support_request xatosi: {e}")
            return None
    
    def get_support_requests(self, status: str = None, user_id: int = None) -> List[Dict[str, Any]]:
        try:
            query = '''
                SELECT sr.*, u.username, u.full_name 
                FROM support_requests sr
                JOIN users u ON sr.user_id = u.user_id
            '''
            params = []
            
            conditions = []
            if status:
                conditions.append("sr.status = ?")
                params.append(status)
            if user_id:
                conditions.append("sr.user_id = ?")
                params.append(user_id)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY sr.created_at DESC"
            
            self.cursor.execute(query, params)
            results = self.cursor.fetchall()
            
            requests = []
            for row in results:
                requests.append({
                    'id': row[0],
                    'user_id': row[1],
                    'status': row[2],
                    'subject': row[3],
                    'last_message': row[4],
                    'created_at': row[5],
                    'updated_at': row[6],
                    'username': row[7],
                    'full_name': row[8]
                })
            return requests
        except Exception as e:
            print(f"❌ get_support_requests xatosi: {e}")
            return []
    
    def get_support_request(self, request_id: int) -> Optional[Dict[str, Any]]:
        try:
            self.cursor.execute('''
                SELECT sr.*, u.username, u.full_name, u.user_id
                FROM support_requests sr
                JOIN users u ON sr.user_id = u.user_id
                WHERE sr.id = ?
            ''', (request_id,))
            
            result = self.cursor.fetchone()
            if result:
                return {
                    'id': result[0],
                    'user_id': result[1],
                    'status': result[2],
                    'subject': result[3],
                    'last_message': result[4],
                    'created_at': result[5],
                    'updated_at': result[6],
                    'username': result[7],
                    'full_name': result[8]
                }
            return None
        except Exception as e:
            print(f"❌ get_support_request xatosi: {e}")
            return None
    
    def get_support_conversation(self, request_id: int) -> List[Dict[str, Any]]:
        try:
            self.cursor.execute('''
                SELECT sc.*, u.username, u.full_name
                FROM support_conversations sc
                LEFT JOIN users u ON sc.sender_id = u.user_id
                WHERE sc.request_id = ?
                ORDER BY sc.created_at ASC
            ''', (request_id,))
            
            results = self.cursor.fetchall()
            messages = []
            for row in results:
                messages.append({
                    'id': row[0],
                    'request_id': row[1],
                    'sender_id': row[2],
                    'message_text': row[3],
                    'is_from_user': bool(row[4]),
                    'created_at': row[5],
                    'username': row[6],
                    'full_name': row[7]
                })
            return messages
        except Exception as e:
            print(f"❌ get_support_conversation xatosi: {e}")
            return []
    
    def add_support_message(self, request_id: int, sender_id: int, message: str, is_from_user: bool) -> bool:
        try:
            self.cursor.execute('''INSERT INTO support_conversations 
                                (request_id, sender_id, message_text, is_from_user, created_at)
                                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                                (request_id, sender_id, message, is_from_user))
            
            self.cursor.execute('''UPDATE support_requests 
                                SET last_message = ?, updated_at = CURRENT_TIMESTAMP
                                WHERE id = ?''', (message[:200], request_id))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ add_support_message xatosi: {e}")
            return False
    
    def get_unread_messages_count(self, user_id: int = None, is_admin: bool = False) -> int:
        try:
            if is_admin:
                self.cursor.execute('''
                    SELECT COUNT(*) FROM messages 
                    WHERE is_from_user = 1 AND is_read = 0
                ''')
            else:
                self.cursor.execute('''
                    SELECT COUNT(*) FROM messages 
                    WHERE user_id = ? AND is_from_user = 0 AND is_read = 0
                ''', (user_id,))
            
            result = self.cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            print(f"❌ get_unread_messages_count xatosi: {e}")
            return 0
    
    def get_stats(self) -> Tuple[int, int, int]:
        try:
            users = self.cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            groups = self.cursor.execute("SELECT COUNT(*) FROM groups").fetchone()[0]
            threats = self.cursor.execute("SELECT COUNT(*) FROM logs WHERE threat_level != 'Safe'").fetchone()[0]
            return users, groups, threats
        except Exception as e:
            print(f"❌ get_stats xatosi: {e}")
            return 0, 0, 0
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        try:
            self.cursor.execute('''
                SELECT 
                    u.user_id,
                    u.username,
                    u.full_name,
                    u.trust_score,
                    u.created_at,
                    COUNT(l.id) as total_messages,
                    SUM(CASE WHEN l.threat_level != 'Safe' THEN 1 ELSE 0 END) as threat_messages,
                    MAX(l.created_at) as last_activity
                FROM users u
                LEFT JOIN logs l ON u.user_id = l.user_id
                WHERE u.user_id = ?
                GROUP BY u.user_id
            ''', (user_id,))
            
            result = self.cursor.fetchone()
            if result:
                return {
                    'user_id': result[0],
                    'username': result[1],
                    'full_name': result[2],
                    'trust_score': result[3],
                    'created_at': result[4],
                    'total_messages': result[5] or 0,
                    'threat_messages': result[6] or 0,
                    'last_activity': result[7]
                }
            return {}
        except Exception as e:
            print(f"❌ get_user_stats xatosi: {e}")
            return {}
    
    def get_daily_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        try:
            self.cursor.execute('''
                SELECT 
                    date(created_at),
                    COUNT(*) as total_messages,
                    SUM(CASE WHEN threat_level = 'Safe' THEN 1 ELSE 0 END) as safe_messages,
                    SUM(CASE WHEN threat_level != 'Safe' THEN 1 ELSE 0 END) as threat_messages
                FROM logs
                WHERE created_at >= date('now', ?)
                GROUP BY date(created_at)
                ORDER BY date(created_at) DESC
            ''', (f'-{days} days',))
            
            results = self.cursor.fetchall()
            stats = []
            for row in results:
                stats.append({
                    'date': row[0],
                    'total_messages': row[1],
                    'safe_messages': row[2],
                    'threat_messages': row[3]
                })
            return stats
        except Exception as e:
            print(f"❌ get_daily_stats xatosi: {e}")
            return []
    
    def get_recent_threats(self, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            self.cursor.execute('''
                SELECT 
                    l.id,
                    l.group_id,
                    l.user_id,
                    l.message_text,
                    l.threat_level,
                    l.created_at,
                    u.username,
                    u.full_name,
                    g.group_name
                FROM logs l
                LEFT JOIN users u ON l.user_id = u.user_id
                LEFT JOIN groups g ON l.group_id = g.group_id
                WHERE l.threat_level != 'Safe'
                ORDER BY l.created_at DESC
                LIMIT ?
            ''', (limit,))
            
            results = self.cursor.fetchall()
            threats = []
            for row in results:
                threats.append({
                    'id': row[0],
                    'group_id': row[1],
                    'user_id': row[2],
                    'message_text': row[3],
                    'threat_level': row[4],
                    'created_at': row[5],
                    'username': row[6],
                    'full_name': row[7],
                    'group_name': row[8]
                })
            return threats
        except Exception as e:
            print(f"❌ get_recent_threats xatosi: {e}")
            return []
    def update_support_request(self, request_id: int, status: str, message: str = None) -> bool:
        """Support request ni yangilash"""
        try:
            if message:
                self.cursor.execute('''UPDATE support_requests 
                                    SET status = ?, last_message = ?, updated_at = CURRENT_TIMESTAMP
                                    WHERE id = ?''', (status, message[:200], request_id))
            else:
                self.cursor.execute('''UPDATE support_requests 
                                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                                    WHERE id = ?''', (status, request_id))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ update_support_request xatosi: {e}")
            return False
    
    def ban_user(self, user_id: int) -> bool:
        try:
            self.cursor.execute('''UPDATE users SET 
                                is_banned = 1, trust_score = 0
                                WHERE user_id = ?''', (user_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ ban_user xatosi: {e}")
            return False
    
    def unban_user(self, user_id: int) -> bool:
        try:
            self.cursor.execute('''UPDATE users SET 
                                is_banned = 0, trust_score = 100
                                WHERE user_id = ?''', (user_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ unban_user xatosi: {e}")
            return False
    
    def close(self):
        try:
            self.conn.close()
            print("✅ Ma'lumotlar bazasi yopildi")
        except Exception as e:
            print(f"❌ close xatosi: {e}")

# Global obyekt
db = Database()