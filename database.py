import sqlite3
# Для aiogram 3.x и современных практик используем контекстный менеджер для подключения
# и создаем таблицу пользователей при импорте.

DB_PATH = "users.db"

def init_db():
    """Инициализация базы данных и создание таблицы пользователей, если ее нет."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id   INTEGER PRIMARY KEY,
                username  TEXT
            )
        """)
        conn.commit()


def add_user(user_id: int, username: str):
    """Добавляет нового пользователя или обновляет username, если запись уже существует."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        conn.commit()

# Инициализируем базу при загрузке модуля
init_db()