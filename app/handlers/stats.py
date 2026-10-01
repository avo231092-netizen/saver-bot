from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app import db

router = Router()

def back_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅ В меню", callback_data="back_main")
    return kb.as_markup()

async def show_stats(message, edit=False):
    subs = await db.list_subscriptions(message.from_user.id if hasattr(message, 'from_user') else message.chat.id)
    items = await db.list_tracked_items(message.from_user.id if hasattr(message, 'from_user') else message.chat.id)
    total_monthly = sum(s[2] for s in subs if s[4] == 'monthly')
    total_yearly = sum(s[2] for s in subs if s[4] == 'yearly')
    total = total_monthly * 12 + total_yearly
    text = (
        "<b>📊 Статистика</b>\n\n"
        f"Подписок активно: {len(subs)}\n"
        f"Товаров в отслеживании: {len(items)}\n\n"
        f"Расходы в месяц: {total_monthly:.0f}₽\n"
        f"Расходы в год: {total:.0f}₽\n"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅ В меню", callback_data="back_main")
    if edit:
        await message.edit_text(text, reply_markup=kb.as_markup())
    else:
        await message.answer(text, reply_markup=kb.as_markup())

@router.callback_query(F.data == "back_main")
async def cb_back_main(call: CallbackQuery):
    from app.bot import main_menu_kb
    await call.message.edit_text("Выбери раздел:", reply_markup=main_menu_kb())
    await call.answer()

async def register(dp):
    dp.include_router(router)
