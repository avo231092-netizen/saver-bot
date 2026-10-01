import aiosqlite
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "/app/data/saver.db")

async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                cost REAL NOT NULL,
                currency TEXT DEFAULT 'RUB',
                cycle TEXT DEFAULT 'monthly',
                next_payment TEXT NOT NULL,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tracked_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                title TEXT,
                marketplace TEXT,
                last_price REAL,
                target_price REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, url)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                price REAL NOT NULL,
                checked_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES tracked_items(id)
            )
        """)
        await db.commit()

async def add_subscription(user_id, name, cost, next_payment, cycle='monthly', currency='RUB'):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO subscriptions (user_id, name, cost, currency, cycle, next_payment) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, name, cost, currency, cycle, next_payment)
        )
        await db.commit()

async def list_subscriptions(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, name, cost, currency, cycle, next_payment FROM subscriptions WHERE user_id=? AND active=1 ORDER BY next_payment",
            (user_id,)
        ) as cur:
            return await cur.fetchall()

async def cancel_subscription(user_id, sub_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE subscriptions SET active=0 WHERE id=? AND user_id=?",
            (sub_id, user_id)
        )
        await db.commit()

async def add_tracked_item(user_id, url, title, marketplace, last_price, target_price=None):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO tracked_items (user_id, url, title, marketplace, last_price, target_price) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, url, title, marketplace, last_price, target_price)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def list_tracked_items(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, url, title, marketplace, last_price, target_price FROM tracked_items WHERE user_id=?",
            (user_id,)
        ) as cur:
            return await cur.fetchall()

async def update_price(item_id, new_price):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tracked_items SET last_price=? WHERE id=?",
            (new_price, item_id)
        )
        await db.execute(
            "INSERT INTO price_history (item_id, price) VALUES (?, ?)",
            (item_id, new_price)
        )
        await db.commit()

async def get_due_subscriptions():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT user_id, name, cost, currency, next_payment FROM subscriptions
               WHERE active=1 AND date(next_payment) <= date('now', '+3 days')
               ORDER BY next_payment"""
        ) as cur:
            return await cur.fetchall()

async def get_all_tracked_items():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, user_id, url, title, marketplace, last_price FROM tracked_items"
        ) as cur:
            return await cur.fetchall()
