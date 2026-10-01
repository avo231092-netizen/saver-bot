import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
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
    kb.button(text="📬 Контакты", callback_data="menu_contacts")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def back_to_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅ В главное меню", callback_data="back_to_main")
    return kb.as_markup()


WELCOME_TEXT = (
    "Привет! Я <b>SaverBot</b> 🐿 — твой личный финансовый помощник.\n\n"
    "Я помогу тебе экономить деньги и не забывать о важных списаниях.\n\n"
    "<b>Что я умею:</b>\n"
    "📋 <b>Подписки</b> — добавляй свои подписки (Netflix, Spotify, iCloud, gym и т.д.), "
    "и я напомню за 3 дня до списания, чтобы ты успел отменить ненужное.\n"
    "💰 <b>Цены</b> — пришли ссылку на товар с Wildberries или Ozon, и я прослежу за ценой. "
    "Как только она упадёт — сразу напишу тебе.\n"
    "📊 <b>Статистика</b> — покажу, сколько ты тратишь на подписки в месяц и в год.\n\n"
    "<i>Выбери раздел ниже, чтобы начать:</i>"
)


HELP_TEXT = (
    "<b>Как пользоваться SaverBot</b> 🐿\n\n"
    "<b>📋 Подписки</b>\n"
    "Добавляй все свои платные подписки — Netflix, Spotify, iCloud, Яндекс.Плюс, "
    "спортзал, курсы, VPN. Укажи стоимость и дату следующего списания. "
    "За 3 дня до списания я пришлю напоминание, чтобы ты успел решить: "
    "оставить подписку или отменить.\n\n"
    "<i>Команды:</i> /add — добавить, /list — список, /cancel — отменить.\n\n"
    "<b>💰 Цены</b>\n"
    "Увидел товар на Wildberries или Ozon, который хочешь купить, но цена кусается? "
    "Пришли ссылку — я буду проверять цену каждый час. Как только она снизится, "
    "ты получишь уведомление с указанием размера скидки.\n\n"
    "<i>Команды:</i> /track — отслеживать, /tracked — список товаров.\n\n"
    "<b>📊 Статистика</b>\n"
    "Покажу общую картину твоих расходов: сколько подписок активно, "
    "сколько ты платишь в месяц и в год.\n\n"
    "<i>Команда:</i> /stats.\n\n"
    "<b>💡 Совет</b>\n"
    "Добавь все свои подписки прямо сейчас — так ты не забудешь ни про одно списание. "
    "А товары, которые хочешь купить дешевле, добавляй в отслеживание — я сам пришлю "
    "уведомление, когда цена упадёт."
)


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT)


@dp.callback_query(F.data == "menu_help")
async def cb_help(call: CallbackQuery):
    await call.message.edit_text(HELP_TEXT, reply_markup=back_to_menu_kb())
    await call.answer()


@dp.callback_query(F.data == "menu_contacts")
async def cb_contacts(call: CallbackQuery):
    text = (
        "<b>📬 Контакты</b>\n\n"
        "По всем вопросам, идеям и предложениям:\n"
        "• Telegram: @your_support\n"
        "• Email: support@saverbot.ru\n\n"
        "<i>Бот создан с помощью Mira AI.</i>"
    )
    await call.message.edit_text(text, reply_markup=back_to_menu_kb())
    await call.answer()


@dp.callback_query(F.data == "menu_subs")
async def cb_subs(call: CallbackQuery):
    await subscriptions.show_subscriptions_menu(call.message, edit=True)
    await call.answer()


@dp.callback_query(F.data == "menu_prices")
async def cb_prices(call: CallbackQuery):
    await prices.show_prices_menu(call.message, edit=True)
    await call.answer()


@dp.callback_query(F.data == "menu_stats")
async def cb_stats(call: CallbackQuery):
    await stats.show_stats(call.message, edit=True)
    await call.answer()


@dp.callback_query(F.data == "back_to_main")
async def cb_back_to_main(call: CallbackQuery):
    await call.message.edit_text(WELCOME_TEXT, reply_markup=main_menu_kb())
    await call.answer()


async def main():
    await db.init_db()
    dp.include_router(subscriptions.router)
    dp.include_router(prices.router)
    dp.include_router(stats.router)
    start_scheduler(bot)
    logger.info("SaverBot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
