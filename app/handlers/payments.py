from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, LabeledPrice
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from app import db

router = Router()

# Pricing in Telegram Stars (XTR)
PLANS = {
    "trial": {"days": 7, "stars": 0, "title": "🎁 Пробный период", "desc": "7 дней бесплатно"},
    "month": {"days": 30, "stars": 100, "title": "⭐ 1 месяц Premium", "desc": "30 дней полного доступа"},
    "year": {"days": 365, "stars": 999, "title": "⭐ 1 год Premium", "desc": "365 дней (выгода 17%)"},
}


class PromoState(StatesGroup):
    code = State()


def plans_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎁 Активировать пробный", callback_data="plan_trial")
    kb.button(text="⭐ 1 месяц — 100⭐", callback_data="plan_month")
    kb.button(text="⭐ 1 год — 999⭐", callback_data="plan_year")
    kb.button(text="🎟 Ввести промокод", callback_data="plan_promo")
    kb.button(text="⬅ В меню", callback_data="back_to_main")
    kb.adjust(1, 2, 1, 1)
    return kb.as_markup()


def back_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅ Назад", callback_data="menu_pricing")
    return kb.as_markup()


async def show_pricing_menu(message, edit=False):
    user_id = message.from_user.id if hasattr(message, 'from_user') and message.from_user else message.chat.id
    user = await db.get_user(user_id)
    tier = user[0] if user else 'free'
    now = datetime.utcnow().strftime("%Y-%m-%d")
    status_text = ""
    if tier == 'premium' and user[2] and user[2] >= now:
        status_text = f"\n\n💎 У тебя активен <b>Premium</b> до {user[2]}"
    elif tier == 'trial' and user[1] and user[1] >= now:
        status_text = f"\n\n🎁 У тебя <b>пробный период</b> до {user[1]}"
    else:
        status_text = "\n\n🆓 У тебя <b>бесплатный тариф</b>: 5 подписок, 3 товара"

    text = (
        "<b>💎 Тарифы SaverBot</b>\n\n"
        "🆓 <b>Бесплатно</b>\n"
        "• 5 подписок\n"
        "• 3 товара в отслеживании\n"
        "• Базовая статистика\n\n"
        "⭐ <b>Premium</b>\n"
        "• Безлимит подписок и товаров\n"
        "• Расширенная статистика\n"
        "• Приоритетные напоминания\n"
        "• Доступ ко всем новым функциям\n"
        f"{status_text}"
    )
    if edit:
        await message.edit_text(text, reply_markup=plans_kb())
    else:
        await message.answer(text, reply_markup=plans_kb())


@router.callback_query(F.data == "plan_trial")
async def cb_plan_trial(call: CallbackQuery):
    user = await db.get_user(call.from_user.id)
    if user and user[0] == 'trial':
        await call.answer("Пробный период уже использован", show_alert=True)
        return
    if user and user[0] == 'premium':
        await call.answer("У тебя уже Premium", show_alert=True)
        return
    await db.set_user_tier(call.from_user.id, 'trial', 7)
    await call.message.edit_text(
        "🎉 <b>Пробный период активирован!</b>\n\n"
        "У тебя 7 дней полного доступа.\n"
        "Добавляй сколько угодно подписок и товаров!\n\n"
        "После окончания пробного периода ты сможешь оформить Premium звёздами Telegram.",
        reply_markup=back_kb()
    )
    await call.answer()


@router.callback_query(F.data == "plan_month")
async def cb_plan_month(call: CallbackQuery):
    await send_invoice(call.message, call.from_user.id, "month")
    await call.answer()


@router.callback_query(F.data == "plan_year")
async def cb_plan_year(call: CallbackQuery):
    await send_invoice(call.message, call.from_user.id, "year")
    await call.answer()


async def send_invoice(message, user_id, plan_key):
    plan = PLANS[plan_key]
    payment_id = await db.create_payment(user_id, plan["stars"], 'premium', plan["days"])
    await message.answer_invoice(
        title=plan["title"],
        description=plan["desc"],
        payload=f"saver_{payment_id}",
        currency="XTR",
        prices=[LabeledPrice(label=plan["title"], amount=plan["stars"])]
    )


@router.pre_checkout_query()
async def pre_checkout(query):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def on_success(message: Message):
    payload = message.successful_payment.invoice_payload
    if payload.startswith("saver_"):
        payment_id = int(payload.split("_")[1])
        await db.complete_payment(payment_id, message.successful_payment.telegram_payment_charge_id)
        await message.answer(
            "🎉 <b>Оплата получена!</b>\n\n"
            "Premium активирован. Спасибо за поддержку!\n"
            "Теперь у тебя безлимитный доступ ко всем функциям."
        )


@router.callback_query(F.data == "plan_promo")
async def cb_plan_promo(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "Пришли промокод:",
        reply_markup=back_kb()
    )
    await state.set_state(PromoState.code)
    await call.answer()


@router.message(PromoState.code)
async def proc_promo(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    ok, msg = await db.redeem_promo(message.from_user.id, code)
    await state.clear()
    await message.answer(msg, reply_markup=back_kb())


async def register(dp):
    dp.include_router(router)
