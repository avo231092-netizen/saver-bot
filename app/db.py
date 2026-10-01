import aiosqlite
import os
from datetime import datetime, timedelta

DB_PATH = os.getenv("DB_PATH", "/app/data/saver.db")

FREE_SUB_LIMIT = 5
FREE_TRACK_LIMIT = 3
TRIAL_DAYS = 7

async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        # Existing tables
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
        # NEW: users with subscription tier
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                tier TEXT DEFAULT 'free',
                trial_until TEXT,
                premium_until TEXT,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                stars_balance INTEGER DEFAULT 0
            )
        """)
        # NEW: payments log
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT DEFAULT 'XTR',
                status TEXT DEFAULT 'pending',
                tier TEXT,
                days INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                telegram_charge_id TEXT,
                completed_at TEXT
            )
        """)
        # NEW: admin-configurable sections
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                emoji TEXT,
                is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # NEW: promo codes
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                tier TEXT DEFAULT 'premium',
                days INTEGER NOT NULL,
                uses_left INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Seed default sections
        await db.executescript("""
            INSERT OR IGNORE INTO sections (key, title, description, emoji, sort_order) VALUES
            ('subs', 'Подписки', 'Отслеживание подписок и напоминания', '📋', 1),
            ('prices', 'Цены', 'Отслеживание цен на WB и Ozon', '💰', 2),
            ('stats', 'Статистика', 'Аналитика расходов', '📊', 3);
        """)
        await db.commit()


# === USER ===
async def get_user(user_id, username=None, first_name=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
            (user_id, username, first_name)
        )
        await db.commit()
        async with db.execute("SELECT tier, trial_until, premium_until, stars_balance FROM users WHERE user_id=?", (user_id,)) as cur:
            return await cur.fetchone()

async def set_user_tier(user_id, tier, days=None):
    async with aiosqlite.connect(DB_PATH) as db:
        if tier == 'trial':
            until = (datetime.utcnow() + timedelta(days=days or TRIAL_DAYS)).strftime("%Y-%m-%d")
            await db.execute("UPDATE users SET tier=?, trial_until=? WHERE user_id=?", (tier, until, user_id))
        elif tier == 'premium':
            # Extend or set premium
            async with db.execute("SELECT premium_until FROM users WHERE user_id=?", (user_id,)) as cur:
                row = await cur.fetchone()
            if row and row[0]:
                try:
                    current = datetime.strptime(row[0], "%Y-%m-%d")
                    if current > datetime.utcnow():
                        until = (current + timedelta(days=days)).strftime("%Y-%m-%d")
                    else:
                        until = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")
                except:
                    until = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")
            else:
                until = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")
            await db.execute("UPDATE users SET tier=?, premium_until=? WHERE user_id=?", (tier, until, user_id))
        elif tier == 'free':
            await db.execute("UPDATE users SET tier=?, trial_until=NULL, premium_until=NULL WHERE user_id=?", (tier, user_id))
        await db.commit()

async def check_access(user_id):
    """Returns (has_access, tier, limit_sub, limit_track, message)"""
    user = await get_user(user_id)
    if not user:
        return True, 'free', FREE_SUB_LIMIT, FREE_TRACK_LIMIT, None
    tier, trial_until, premium_until, stars = user
    now = datetime.utcnow().strftime("%Y-%m-%d")
    if tier == 'premium' and premium_until and premium_until >= now:
        return True, 'premium', 999, 999, None
    if tier == 'trial' and trial_until and trial_until >= now:
        return True, 'trial', 999, 999, None
    if tier == 'premium' and premium_until and premium_until < now:
        return True, 'free', FREE_SUB_LIMIT, FREE_TRACK_LIMIT, "⏰ Premium закончился. Перейди на бесплатный тариф."
    if tier == 'trial' and trial_until and trial_until < now:
        return True, 'free', FREE_SUB_LIMIT, FREE_TRACK_LIMIT, "⏰ Пробный период закончился."
    return True, 'free', FREE_SUB_LIMIT, FREE_TRACK_LIMIT, None

async def count_subscriptions(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM subscriptions WHERE user_id=? AND active=1", (user_id,)) as cur:
            r = await cur.fetchone()
            return r[0] if r else 0

async def count_tracked_items(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM tracked_items WHERE user_id=?", (user_id,)) as cur:
            r = await cur.fetchone()
            return r[0] if r else 0

# === SUBSCRIPTIONS ===
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

# === TRACKED ITEMS ===
async def add_tracked_item(user_id, url, title, marketplace, last_price, target_price=None):
    async with aiosCRite.connect(DB_PATH) as db:
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

# === PAYMENTS ===
async def create_payment(user_id, amount, tier, days):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO payments (user_id, amount, currency, tier, days, status) VALUES (?, ?, 'XTR', ?, ?, 'pending')",
            (user_id, amount, tier, days)
        )
        await db.commit()
        return cur.lastrowid

async def complete_payment(payment_id, telegram_charge_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, tier, days FROM payments WHERE id=?", (payment_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            return
        user_id, tier, days = row
        await db.execute(
            "UPDATE payments SET status='completed', telegram_charge_id=?, completed_at=CURRENT_TIMESTAMP WHERE id=?",
            (telegram_charge_id, payment_id)
        )
        await db.commit()
        await set_user_tier(user_id, tier, days)

# === SECTIONS (admin) ===
async def list_sections():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, key, title, description, emoji, is_active, sort_order FROM sections ORDER BY sort_order") as cur:
            return await cur.fetchall()

async def toggle_section(section_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE sections SET is_active = 1 - is_active WHERE id=?", (section_id,))
        await db.commit()

async def add_section(key, title, description, emoji):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO sections (key, title, description, emoji) VALUES (?, ?, ?, ?)",
                (key, title, description, emoji)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def delete_section(section_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sections WHERE id=?", (section_id,))
        dynamic = await db.execute("DELETE FROM sections WHERE id=?", (section_id,))
        await db.commit()

# === PROMO CODES ===
async def redeem_promo(user_id, code):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT tier, days, uses_left FROM promo_codes WHERE code=?", (code,)) as cur:
            row = await cur.fetchone()
        if not row:
            return False, "Промокод не найден"
        tier, days, uses_left = row
        if uses_left <= 0:
            return False, "Промокод уже использован"
        await db.execute("UPDATE promo_codes SET uses_left = uses_left - 1 WHERE code=?", (code,))
        await db.commit()
    await set_user_tier(user_id, tier, days)
    return True, f"✅ Активирован {tier} на {days} дней"

# === ADMIN STATS ===
async def get_admin_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total_users = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE tier='premium' AND premium_until >= date('now')") as cur:
            premium_users = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE tier='trial' AND trial_until >= date('now')") as cur:
            trial_users = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM subscriptions WHERE active=1") as cur:
            total_subs = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM tracked_items") as cur:
            total_items = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM payments WHERE status='completed'") as cur:
            total_payments = (await cur.fetchone())[0]
        async with db.execute("SELECT SUM(amount) FROM payments WHERE status='completed'") as cur:
            total_stars = (await cur.fetchone())[0] or 0
        return {
            'total_users': total_users,
            'premium_users': premium_users,
            'trial_users': trial_users,
            'total_subs': total_subs,
            'total_items': total_items,
    }
