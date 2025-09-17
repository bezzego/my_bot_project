import sqlite3

# Connect to SQLite database (will create users.db if it doesn't exist)
conn = sqlite3.connect("users.db")
cursor = conn.cursor()

# Create table for storing users (user_id is unique primary key, username stored for reference)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id   INTEGER PRIMARY KEY,
        username  TEXT
    )
""")
conn.commit()

def add_user(user_id: int, username: str):
    """Add a new user or update username if the user already exists."""
    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, username) VALUES (?, ?)",
        (user_id, username)
    )
    conn.commit()