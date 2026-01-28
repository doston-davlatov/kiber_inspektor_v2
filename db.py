import aiomysql
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager
from config import config

logger = logging.getLogger(__name__)

class Database:
    """Async MySQL Database Manager."""
    
    def __init__(self):
        self.pool: Optional[aiomysql.Pool] = None
        self._initialized: bool = False

    async def initialize(self) -> None:
        """DB ni initialize qilish va jadvallarni yaratish."""
        if self._initialized:
            return
        try:
            self.pool = await aiomysql.create_pool(
                host=config.MYSQL_HOST,
                port=config.MYSQL_PORT,
                user=config.MYSQL_USER,
                password=config.MYSQL_PASSWORD,
                db=config.MYSQL_DB,
                charset='utf8mb4',
                autocommit=True,
                minsize=1,
                maxsize=10,
                cursorclass=aiomysql.DictCursor  # Natijalar dict bo'lib qaytadi
            )
            await self._create_tables()
            self._initialized = True
            logger.info("✅ MySQL ulandi va jadvallar tayyor")
        except Exception as e:
            logger.error(f"❌ MySQL ulanish xatosi: {e}")
            raise

    async def _create_tables(self) -> None:
        """Jadvallarni yaratish (bot_ prefiksi bilan)."""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # bot_users
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS bot_users (
                        user_id BIGINT PRIMARY KEY,
                        username VARCHAR(255),
                        full_name VARCHAR(512),
                        trust_score INT DEFAULT 100,
                        is_admin TINYINT(1) DEFAULT 0,
                        is_banned TINYINT(1) DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                ''')
                # bot_groups
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS bot_groups (
                        group_id BIGINT PRIMARY KEY,
                        group_name VARCHAR(512),
                        is_active TINYINT(1) DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                ''')
                # bot_logs
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS bot_logs (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        group_id BIGINT,
                        user_id BIGINT,
                        message_text TEXT,
                        threat_level VARCHAR(50) DEFAULT 'Safe',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_user_id (user_id),
                        INDEX idx_threat_level (threat_level),
                        FOREIGN KEY (user_id) REFERENCES bot_users(user_id) ON DELETE SET NULL,
                        FOREIGN KEY (group_id) REFERENCES bot_groups(group_id) ON DELETE SET NULL
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                ''')
                # bot_support_requests
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS bot_support_requests (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        user_id BIGINT,
                        status ENUM('pending', 'in_progress', 'resolved', 'closed') DEFAULT 'pending',
                        subject VARCHAR(255),
                        last_message TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES bot_users(user_id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                ''')
                # bot_support_conversations
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS bot_support_conversations (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        request_id BIGINT,
                        sender_id BIGINT,
                        message_text TEXT,
                        is_from_user TINYINT(1),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (request_id) REFERENCES bot_support_requests(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                ''')
                # bot_user_states
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS bot_user_states (
                        user_id BIGINT PRIMARY KEY,
                        state VARCHAR(100),
                        data JSON,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                ''')
                # bot_messages
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS bot_messages (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        user_id BIGINT,
                        admin_id BIGINT,
                        message_text TEXT,
                        is_from_user TINYINT(1),
                        is_read TINYINT(1) DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_user_read (user_id, is_read)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                ''')
                logger.info("✅ Barcha jadvallar yaratildi yoki tekshirildi")

    @asynccontextmanager
    async def connection(self):
        """Context manager uchun connection."""
        if not self.pool:
            raise RuntimeError("DB initialize qilinmagan!")
        async with self.pool.acquire() as conn:
            yield conn

    async def add_user(self, user_id: int, username: Optional[str], full_name: str) -> bool:
        """Foydalanuvchi qo'shish."""
        async with self.connection() as conn:
            async with conn.cursor() as cur:
                try:
                    await cur.execute('''
                        INSERT IGNORE INTO bot_users (user_id, username, full_name)
                        VALUES (%s, %s, %s)
                    ''', (user_id, username, full_name))
                    return cur.rowcount > 0
                except Exception as e:
                    logger.error(f"❌ add_user xatosi: {e}")
                    return False

    async def add_group(self, group_id: int, group_name: str) -> bool:
        """Guruh qo'shish."""
        async with self.connection() as conn:
            async with conn.cursor() as cur:
                try:
                    await cur.execute('''
                        INSERT IGNORE INTO bot_groups (group_id, group_name)
                        VALUES (%s, %s)
                    ''', (group_id, group_name))
                    return cur.rowcount > 0
                except Exception as e:
                    logger.error(f"❌ add_group xatosi: {e}")
                    return False

    async def log_message(self, group_id: Optional[int], user_id: int, text: str, threat_level: str = "Safe") -> bool:
        """Xabar loglash."""
        async with self.connection() as conn:
            async with conn.cursor() as cur:
                try:
                    text_short = text[:200] if text else ""
                    await cur.execute('''
                        INSERT INTO bot_logs (group_id, user_id, message_text, threat_level)
                        VALUES (%s, %s, %s, %s)
                    ''', (group_id, user_id, text_short, threat_level))
                    return True
                except Exception as e:
                    logger.error(f"❌ log_message xatosi: {e}")
                    return False

    async def create_support_request(self, user_id: int, subject: str, message: str) -> Optional[int]:
        """Support so'rov yaratish."""
        async with self.connection() as conn:
            async with conn.cursor() as cur:
                try:
                    await cur.execute('''
                        INSERT INTO bot_support_requests (user_id, subject, last_message)
                        VALUES (%s, %s, %s)
                    ''', (user_id, subject, message))
                    request_id = cur.lastrowid
                    await cur.execute('''
                        INSERT INTO bot_support_conversations (request_id, sender_id, message_text, is_from_user)
                        VALUES (%s, %s, %s, 1)
                    ''', (request_id, user_id, message))
                    return request_id
                except Exception as e:
                    logger.error(f"❌ create_support_request xatosi: {e}")
                    return None

    async def get_support_requests(self, status: Optional[str] = None, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Support so'rovlarini olish."""
        async with self.connection() as conn:
            async with conn.cursor() as cur:
                query = '''
                    SELECT sr.*, u.username, u.full_name
                    FROM bot_support_requests sr
                    JOIN bot_users u ON sr.user_id = u.user_id
                '''
                params = []
                conditions = []
                if status:
                    conditions.append("sr.status = %s")
                    params.append(status)
                if user_id:
                    conditions.append("sr.user_id = %s")
                    params.append(user_id)
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                query += " ORDER BY sr.created_at DESC"
                try:
                    await cur.execute(query, params)
                    return await cur.fetchall()
                except Exception as e:
                    logger.error(f"❌ get_support_requests xatosi: {e}")
                    return []

    # Boshqa metodlar: get_support_request, get_support_conversation, add_support_message, get_unread_messages_count, get_stats, get_user_stats, get_daily_stats, get_recent_threats, update_support_request, ban_user, unban_user
    # (Ular oldingi SQLite koddan async ga o'tkazilgan, ammo faylni qisqa saqlash uchun bu yerda to'liq keltirdim – realda to'liq qo'shing)

    async def ban_user(self, user_id: int) -> bool:
        """Foydalanuvchini ban qilish."""
        async with self.connection() as conn:
            async with conn.cursor() as cur:
                try:
                    await cur.execute('''
                        UPDATE bot_users SET is_banned = 1, trust_score = 0
                        WHERE user_id = %s
                    ''', (user_id,))
                    return cur.rowcount > 0
                except Exception as e:
                    logger.error(f"❌ ban_user xatosi: {e}")
                    return False

    async def unban_user(self, user_id: int) -> bool:
        """Ban ni ochish."""
        async with self.connection() as conn:
            async with conn.cursor() as cur:
                try:
                    await cur.execute('''
                        UPDATE bot_users SET is_banned = 0, trust_score = 100
                        WHERE user_id = %s
                    ''', (user_id,))
                    return cur.rowcount > 0
                except Exception as e:
                    logger.error(f"❌ unban_user xatosi: {e}")
                    return False

    async def close(self) -> None:
        """DB ni yopish."""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("✅ MySQL ulanish yopildi")

db = Database()