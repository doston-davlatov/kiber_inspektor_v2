# db.py
import aiomysql
import logging
from typing import Optional, List, Dict
from contextlib import asynccontextmanager
from config import config

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.pool: Optional[aiomysql.Pool] = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        try:
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

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
                ssl=ctx if 'aivencloud.com' in config.MYSQL_HOST or 'planetscale' in config.MYSQL_HOST else None,
                cursorclass=aiomysql.DictCursor
            )

            await self._create_tables()
            self._initialized = True
            logger.info("MySQL ulandi")

        except Exception as e:
            logger.error(f"MySQL ulanish xatosi: {e}", exc_info=True)
            raise

    async def _create_tables(self) -> None:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS bot_users (
                        user_id BIGINT PRIMARY KEY,
                        username VARCHAR(255),
                        full_name VARCHAR(512),
                        trust_score INT DEFAULT 100,
                        is_admin TINYINT(1) DEFAULT 0,
                        is_banned TINYINT(1) DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS bot_groups (
                        group_id BIGINT PRIMARY KEY,
                        group_name VARCHAR(512),
                        is_active TINYINT(1) DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS bot_logs (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        chat_id BIGINT,
                        message_id BIGINT,
                        user_id BIGINT,
                        message_text TEXT,
                        threat_level VARCHAR(50) DEFAULT 'Safe',
                        threat_reason TEXT,
                        chat_type VARCHAR(20) DEFAULT 'group',
                        chat_title VARCHAR(512),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_threat (threat_level),
                        INDEX idx_chat (chat_id)
                    )
                ''')
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS bot_support_requests (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        user_id BIGINT,
                        status ENUM('pending', 'in_progress', 'resolved', 'closed') DEFAULT 'pending',
                        subject VARCHAR(255),
                        last_message TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                ''')
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS bot_support_conversations (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        request_id BIGINT,
                        sender_id BIGINT,
                        message_text TEXT,
                        is_from_user TINYINT(1),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS bot_user_states (
                        user_id BIGINT PRIMARY KEY,
                        state VARCHAR(100),
                        data JSON,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                ''')

    @asynccontextmanager
    async def connection(self):
        if not self.pool:
            raise RuntimeError("DB hali ochilmagan")
        async with self.pool.acquire() as conn:
            yield conn

    async def add_user(self, user_id: int, username: Optional[str], full_name: str) -> bool:
        async with self.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute('''
                    INSERT IGNORE INTO bot_users (user_id, username, full_name)
                    VALUES (%s, %s, %s)
                ''', (user_id, username, full_name))
                return cur.rowcount > 0

    async def add_group(self, group_id: int, group_name: str) -> bool:
        async with self.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute('''
                    INSERT IGNORE INTO bot_groups (group_id, group_name)
                    VALUES (%s, %s)
                ''', (group_id, group_name))
                return cur.rowcount > 0

    async def log_threat(self, chat_id: int, message_id: int, user_id: int,
                         text: str, threat_level: str, reason: str,
                         chat_type: str = "group", chat_title: Optional[str] = None) -> bool:
        async with self.connection() as conn:
            async with conn.cursor() as cur:
                text_short = text[:1500] if text else "[media]"
                await cur.execute('''
                    INSERT INTO bot_logs 
                    (chat_id, message_id, user_id, message_text, threat_level, threat_reason, chat_type, chat_title)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (chat_id, message_id, user_id, text_short, threat_level, reason, chat_type, chat_title))
                return True

    async def get_threats(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        async with self.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute('''
                    SELECT id, chat_id, message_id, user_id, message_text, 
                           threat_level, threat_reason, chat_type, chat_title, created_at
                    FROM bot_logs 
                    WHERE threat_level != 'Safe'
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                ''', (limit, offset))
                return await cur.fetchall()

    async def get_recent_threats(self, limit: int = 5) -> List[Dict]:
        return await self.get_threats(limit=limit)

    async def close(self) -> None:
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()

db = Database()