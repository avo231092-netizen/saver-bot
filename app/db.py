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
        async with db.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status='completed'") as cur:
            total_stars = (await cur.fetchone())[0] or 0
        return {
            'total_users': total_users,
            'premium_users': premium_users,
            'trial_users': trial_users,
            'total_subs': total_subs,
            'total_items': total_items,
            'total_payments': total_payments,
            'total_stars': total_stars,
        }
