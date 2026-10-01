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
