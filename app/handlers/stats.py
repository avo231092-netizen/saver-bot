from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app import db

router = Router()


async def show_stats(message, edit=False):
    user_id = message.from_user.id if hasattr(message, 'from_user') and message.from_user else message.chat.id
    subs = await db.list_subscriptions(user_id)
    items = await db.list_tracked_items(user_id)
    total_monthly = sum(s[2] for s in subs if s[4] == 'monthly')
    total_yearly = sum(s[2] for s in subs if s[4] == 'yearly')
    total = total_monthly * 12 + total_yearly
    text = (
        "<b>📊 Твоя статистика</b>\n\n"
        f"📋 Активных подписок: <b>{len(subs)}</b>\n"
        f"💰 Товаров в отслеживании: <b>{len(items)}</b>\n\n"
        f"💸 Расходы в месяц: <b>{total_monthly:.0f}₽</b>\n"
        f"📅 Расходы в год: <b>{total:.0f}₽</b>\n"
    )
    if not subs and not items:
        text += "\n<i>Пока пусто. Добавь первую подписку или товар для отслеживания!</i>"
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅ В главное меню", callback_data="back_to_main")
    if edit:
        await message.edit_text(text, reply_markup=kb.as_markup())
    else:
        await message.answer(text, reply_markup=kb.as_markup())
