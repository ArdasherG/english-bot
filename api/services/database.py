"""
SQLite база данных для хранения профилей пользователей.
Используем aiosqlite для асинхронной работы.
"""
import json
import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "users.db"


async def init_db():
    """Создаёт таблицы если их нет. Вызывается при старте."""
    DB_PATH.parent.mkdir(exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                name        TEXT,
                level       TEXT,       -- beginner / intermediate / advanced
                profession  TEXT,       -- врач, программист, студент...
                interests   TEXT,       -- JSON список: ["аниме", "футбол"]
                goal        TEXT,       -- зачем учит английский
                onboarded      INTEGER DEFAULT 0,
                interface_lang TEXT DEFAULT 'ru',
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            await db.execute("ALTER TABLE users ADD COLUMN interface_lang TEXT DEFAULT 'ru'")
            await db.commit()
        except Exception:
            pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                role        TEXT,   -- user / assistant
                content     TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.commit()


async def get_user(user_id: int) -> dict | None:
    """Возвращает профиль пользователя или None если не найден."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            data = dict(row)
            # Десериализуем interests из JSON
            if data.get("interests"):
                try:
                    data["interests"] = json.loads(data["interests"])
                except Exception:
                    data["interests"] = []
            return data


async def create_user(user_id: int, username: str, name: str) -> None:
    """Создаёт нового пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO users (user_id, username, name)
               VALUES (?, ?, ?)""",
            (user_id, username, name),
        )
        await db.commit()


async def update_user(user_id: int, **fields) -> None:
    """Обновляет поля профиля пользователя."""
    if not fields:
        return

    # Сериализуем interests в JSON если передан списком
    if "interests" in fields and isinstance(fields["interests"], list):
        fields["interests"] = json.dumps(fields["interests"], ensure_ascii=False)

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [user_id]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE users SET {set_clause} WHERE user_id = ?", values
        )
        await db.commit()


async def save_message(user_id: int, role: str, content: str) -> None:
    """Сохраняет сообщение в историю чата."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content),
        )
        await db.commit()


async def get_history(user_id: int, limit: int = 10) -> list[dict]:
    """Возвращает последние N сообщений пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT role, content FROM chat_history
               WHERE user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            # Возвращаем в хронологическом порядке
            return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


async def cleanup_old_history(days: int = 30) -> int:
    """Удаляет сообщения старше N дней. Возвращает кол-во удалённых строк."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM chat_history WHERE created_at < datetime('now', ?)",
            (f"-{days} days",),
        )
        await db.commit()
        return cursor.rowcount
