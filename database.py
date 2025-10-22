import sqlite3
from contextlib import contextmanager
from typing import Iterable, List, Optional, Tuple

# Для aiogram 3.x и современных практик используем контекстный менеджер для подключения
# и создаем таблицы при импорте.

DB_PATH = "users.db"


@contextmanager
def _get_connection():
    """Возвращает подключение к SQLite с включёнными внешними ключами."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Инициализация базы данных и создание всех необходимых таблиц."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id   INTEGER PRIMARY KEY,
                username  TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS channels (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                title           TEXT NOT NULL,
                chat_identifier TEXT NOT NULL,
                invite_link     TEXT,
                magnet_type     TEXT NOT NULL,
                magnet_payload  TEXT NOT NULL,
                magnet_caption  TEXT,
                is_active       INTEGER NOT NULL DEFAULT 1,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS rewards_history (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                channel_id   INTEGER NOT NULL,
                delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, channel_id),
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                FOREIGN KEY (channel_id) REFERENCES channels (id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()


def add_user(user_id: int, username: str):
    """Добавляет нового пользователя или обновляет username, если запись уже существует."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO users (user_id, username)
            VALUES (?, ?)
            """,
            (user_id, username),
        )
        conn.commit()


def add_channel(
    title: str,
    chat_identifier: str,
    invite_link: Optional[str],
    magnet_type: str,
    magnet_payload: str,
    magnet_caption: Optional[str],
) -> int:
    """Создаёт новый канал и возвращает его идентификатор."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO channels (
                title,
                chat_identifier,
                invite_link,
                magnet_type,
                magnet_payload,
                magnet_caption
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, chat_identifier, invite_link, magnet_type, magnet_payload, magnet_caption),
        )
        conn.commit()
        return cursor.lastrowid


def fetch_channels(active_only: bool = True) -> List[sqlite3.Row]:
    """Возвращает список каналов. По умолчанию только активные."""
    query = "SELECT * FROM channels"
    params: Tuple = ()
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY id"
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()


def fetch_channel(channel_id: int) -> Optional[sqlite3.Row]:
    """Возвращает один канал по идентификатору."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM channels WHERE id = ?", (channel_id,))
        return cursor.fetchone()


def update_channel(channel_id: int, **fields) -> bool:
    """Обновляет произвольные поля канала."""
    if not fields:
        return False
    assignments = ", ".join(f"{name} = ?" for name in fields)
    params: Tuple = tuple(fields.values()) + (channel_id,)
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            UPDATE channels
            SET {assignments},
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            params,
        )
        conn.commit()
        return cursor.rowcount > 0


def set_channel_active(channel_id: int, is_active: bool) -> bool:
    """Изменяет статус активности канала."""
    return update_channel(channel_id, is_active=1 if is_active else 0)


def delete_channel(channel_id: int) -> bool:
    """Полностью удаляет канал."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
        conn.commit()
        return cursor.rowcount > 0


def record_reward_delivery(user_id: int, channel_id: int):
    """Записывает факт выдачи литмагнита пользователю."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO rewards_history (user_id, channel_id)
            VALUES (?, ?)
            """,
            (user_id, channel_id),
        )
        conn.commit()


def get_user_count() -> int:
    """Возвращает общее количество пользователей."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        (count,) = cursor.fetchone()
        return count


def get_reward_stats() -> List[sqlite3.Row]:
    """Возвращает статистику выдачи литмагнитов по каналам."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                c.id,
                c.title,
                COUNT(r.id) AS delivered
            FROM channels AS c
            LEFT JOIN rewards_history AS r ON r.channel_id = c.id
            GROUP BY c.id, c.title
            ORDER BY c.id
            """
        )
        return cursor.fetchall()


def get_all_user_ids() -> Iterable[int]:
    """Возвращает идентификаторы всех пользователей для рассылок."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        rows = cursor.fetchall()
    return [row["user_id"] for row in rows]


def get_user_reward_channels(user_id: int) -> List[sqlite3.Row]:
    """Возвращает каналы, из которых пользователь уже получил материалы."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT c.*
            FROM channels AS c
            INNER JOIN rewards_history AS r ON r.channel_id = c.id
            WHERE r.user_id = ?
            ORDER BY r.delivered_at DESC
            """,
            (user_id,),
        )
        return cursor.fetchall()


# Инициализируем базу при загрузке модуля
init_db()
