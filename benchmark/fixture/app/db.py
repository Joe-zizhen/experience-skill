import sqlite3

from . import config
from .security import hash_password

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    full_name TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    is_superuser INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    owner_id INTEGER NOT NULL REFERENCES users(id)
);
"""


def connect(db_path=None):
    conn = sqlite3.connect(db_path or config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    conn.executescript(SCHEMA)
    row = conn.execute("SELECT id FROM users WHERE email = ?", (config.FIRST_SUPERUSER,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO users (email, hashed_password, full_name, is_superuser) VALUES (?, ?, ?, 1)",
            (config.FIRST_SUPERUSER, hash_password(config.FIRST_SUPERUSER_PASSWORD), "Admin"),
        )
    conn.commit()


def get_user_by_email(conn, email):
    return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def get_user(conn, user_id):
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def list_users(conn):
    return conn.execute("SELECT * FROM users ORDER BY id").fetchall()


def create_user(conn, email, password, full_name="", is_superuser=False):
    cur = conn.execute(
        "INSERT INTO users (email, hashed_password, full_name, is_superuser) VALUES (?, ?, ?, ?)",
        (email, hash_password(password), full_name, int(is_superuser)),
    )
    conn.commit()
    return get_user(conn, cur.lastrowid)


def update_user_full_name(conn, user_id, full_name):
    conn.execute("UPDATE users SET full_name = ? WHERE id = ?", (full_name, user_id))
    conn.commit()
    return get_user(conn, user_id)


def list_items(conn, owner_id=None):
    if owner_id is None:
        return conn.execute("SELECT * FROM items ORDER BY id").fetchall()
    return conn.execute("SELECT * FROM items WHERE owner_id = ? ORDER BY id", (owner_id,)).fetchall()


def get_item(conn, item_id):
    return conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()


def create_item(conn, title, description, owner_id):
    cur = conn.execute(
        "INSERT INTO items (title, description, owner_id) VALUES (?, ?, ?)",
        (title, description, owner_id),
    )
    conn.commit()
    return get_item(conn, cur.lastrowid)


def delete_item(conn, item_id):
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
