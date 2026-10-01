import os
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

from app import db
from app.handlers import subscriptions, prices, stats
from app.scheduler import start_scheduler

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Подписки", callback_data="menu_subs")
    kb.button(text="💰 Цены", callback_data="menu_prices")
    kb.button(text="📊 Статистика", callback_data="menu_stats")
    kb.button(text="❓ Помощь", callback_data="menu_help")
    kb.adjust(2, 2)
    return kb.as_markup()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я <b>SaverBot</b> 🐿\n\n"
        "Я помогу отслеживать подписки и цены на товары.\n\n"
        "Выбери раздел:",
        reply_markup=main_menu_kb()
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "<b>SaverBot — команды</b>\n\n"
        "/start — главное меню\n"
        "/add — добавить подписку\n"
        "/list — список подписок\n"
        "/track — отслеживать цену (ответь на ссылку или /track URL)\n"
        "/tracked — список отслеживаемых товаров\n"
        "/stats — статистика\n"
        "/help — эта справка"
    )


@dp.callback_query(lambda c: c.data == "menu_help")
async def cb_help(call):
    await cmd_help(call.message)
    await call.answer()


@dp.callback_query(lambda c: c.data == "menu_subs")
async def cb_subs(call):
    await subscriptions.show_subscriptions_menu(call.message, edit=True)
    await call.answer()


@dp.callback_query(lambda c: c.data == "menu_prices")
async def cb_prices(call):
    await prices.show_prices_menu(call.message, edit=True)
    await call.answer()


@dp.callback_query(lambda c: c.data == "menu_stats")
async def cb_stats(call):
    await stats.show_stats(call.message, edit=True)
    await call.answer()


async def main():
    await db.init_db()
    await subscriptions.register(dp)
    await prices.register(dp)
    await stats.register(dp)
    start_scheduler(bot)
    logger.info("SaverBot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
