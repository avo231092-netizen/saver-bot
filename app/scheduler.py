import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from app import db
from app.parsers import wildberries, ozon

logger = logging.getLogger(__name__)

async def check_subscriptions(bot):
    """Daily 9:00 — remind about subscriptions due in 3 days."""
    try:
        due = await db.get_due_subscriptions()
        if not due:
            return
        by_user = {}
        for user_id, name, cost, currency, next_payment in due:
            by_user.setdefault(user_id, []).append((name, cost, next_payment))
        for user_id, items in by_user.items():
            text = "⏰ <b>Напоминание о подписках</b>\n\n"
            for name, cost, np in items:
                text += f"• <b>{name}</b> — {cost}₽, списание {np}\n"
            text += "\nНе забудьте отменить, если больше не нужно."
            try:
                await bot.send_message(user_id, text)
            except Exception as e:
                logger.warning(f"Cannot send to {user_id}: {e}")
        logger.info(f"Subscription reminders sent to {len(by_user)} users")
    except Exception as e:
        logger.error(f"check_subscriptions error: {e}")

async def check_prices(bot):
    """Hourly — check all tracked items for price drops."""
    try:
        items = await db.get_all_tracked_items()
        if not items:
            return
        for item_id, user_id, url, title, marketplace, last_price in items:
            try:
                if marketplace == "wildberries":
                    info = await wildberries.parse(url)
                elif marketplace == "ozon":
                    info = await ozon.parse(url)
                else:
                    continue
                if not info:
                    continue
                new_price = info["price"]
                if new_price <= 0:
                    continue
                if last_price and new_price < last_price:
                    drop = last_price - new_price
                    pct = (drop / last_price) * 100
                    text = (
                        f"📉 <b>Цена снизилась!</b>\n\n"
                        f"<b>{title}</b>\n"
                        f"Было: {last_price:.0f}₽\n"
                        f"Стало: {new_price:.0f}₽\n"
                        f"Выгода: {drop:.0f}₽ ({pct:.0f}%)\n"
                        f"\n{url}"
                    )
                    try:
                        await bot.send_message(user_id, text)
                    except Exception as e:
                        logger.warning(f"Cannot send to {user_id}: {e}")
                await db.update_price(item_id, new_price)
                await asyncio.sleep(2)  # be polite
            except Exception as e:
                logger.error(f"Price check error for item {item_id}: {e}")
        logger.info(f"Price check done for {len(items)} items")
    except Exception as e:
        logger.error(f"check_prices error: {e}")


def start_scheduler(bot):
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    # Subscriptions: daily at 09:00
    scheduler.add_job(
        check_subscriptions, CronTrigger(hour=9, minute=0), args=[bot], id="subs"
    )
    # Prices: every hour
    scheduler.add_job(
        check_prices, CronTrigger(minute=5), args=[bot], id="prices"
    )
    scheduler.start()
    logger.info("Scheduler started: subs@09:00, prices@hourly")
