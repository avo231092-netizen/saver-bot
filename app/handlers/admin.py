import os
import aiosqlite
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app import db

router = Router()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]


class AdminAuth(StatesGroup):
    password = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика", callback_data="admin_stats")
    kb.button(text="👥 Пользователи", callback_data="admin_users")
    kb.button(text="🎁 Разделы", callback_data="admin_sections")
    kb.button(text="🎟 Промокоды", callback_data="admin_promo")
    kb.button(text="💰 Платежи", callback_data="admin_payments")
    kb.button(text="📢 Рассылка", callback_data="admin_broadcast")
    kb.button(text="🔑 Выдать Premium", callback_data="admin_grant")
    kb.button(text="⬅ В меню", callback_data="back_to_main")
    kb.adjust(2, 2, 2, 1, 1)
    return kb.as_markup()


@router.message(F.text == "/admin")
async def cmd_admin(message: Message, state: FSMContext):
    if is_admin(message.from_user.id):
        await show_admin_panel(message)
    else:
        await message.answer("Введи пароль администратора:")
        await state.set_state(AdminAuth.password)


@router.message(AdminAuth.password)
async def proc_admin_password(message: Message, state: FSMContext):
    if message.text == ADMIN_PASSWORD:
        await state.clear()
        await show_admin_panel(message)
    else:
        await message.answer("❌ Неверный пароль. Попробуй ещё раз:")


async def show_admin_panel(message, edit=False):
    text = (
        "<b>🔐 Админ-панель SaverBot</b>\n\n"
        "Управление ботом, разделами, пользователями и платежами."
    )
    if edit:
        await message.edit_text(text, reply_markup=admin_kb())
    else:
        await message.answer(text, reply_markup=admin_kb())


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    stats = await db.get_admin_stats()
    text = (
        "<b>📊 Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"💎 Premium: <b>{stats['premium_users']}</b>\n"
        f"🎁 Пробный: <b>{stats['trial_users']}</b>\n\n"
        f"📋 Подписок: <b>{stats['total_subs']}</b>\n"
        f"💰 Товаров: <b>{stats['total_items']}</b>\n\n"
        f"💳 Платежей: <b>{stats['total_payments']}</b>\n"
        f"⭐ Звёзд получено: <b>{stats['total_stars']}</b>"
    )
    await call.message.edit_text(text, reply_markup=admin_kb())
    await call.answer()


@router.callback_query(F.data == "admin_sections")
async def cb_admin_sections(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    sections = await db.list_sections()
    text = "<b>🎁 Разделы бота</b>\n\n"
    for s in sections:
        status = "✅" if s[5] else "❌"
        text += f"{status} {s[4]} <b>{s[2]}</b> — {s[3]}\n"
    kb = InlineKeyboardBuilder()
    for s in sections:
        status = "✅" if s[5] else "❌"
        kb.button(text=f"{status} {s[4]} {s[2]}", callback_data=f"sect_toggle_{s[0]}")
    kb.button(text="⬅ Назад", callback_data="admin_back")
    kb.adjust(1)
    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("sect_toggle_"))
async def cb_sect_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    section_id = int(call.data.split("_")[2])
    await db.toggle_section(section_id)
    await cb_admin_sections(call)


@router.callback_query(F.data == "admin_back")
async def cb_admin_back(call: CallbackQuery):
    await show_admin_panel(call.message, edit=True)
    await call.answer()


@router.callback_query(F.data == "admin_promo")
async def cb_admin_promo(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    await call.message.edit_text(
        "<b>🎟 Промокоды</b>\n\n"
        "Пришли код в формате:\n"
        "<code>CODE:days</code>\n\n"
        "Например: <code>NEWUSER30:30</code>\n"
        "Создаст промокод NEWUSER30 на 30 дней Premium.",
        reply_markup=admin_kb()
    )
    await call.answer()


@router.callback_query(F.data == "admin_payments")
async def cb_admin_payments(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    text = (
        "<b>💰 Тарифы</b>\n\n"
        "🎁 <b>Пробный период</b> — 7 дней бесплатно\n"
        "⭐ <b>1 месяц</b> — 100 звёзд\n"
        "⭐ <b>1 год</b> — 999 звёзд (выгода 17%)\n\n"
        "<i>Пользователи могут активировать пробный период один раз."
        "После его окончания они могут оплатить Premium звёздами Telegram.</i>"
    )
    await call.message.edit_text(text, reply_markup=admin_kb())
    await call.answer()


@router.callback_query(F.data == "admin_grant")
async def cb_admin_grant(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    await call.message.edit_text(
        "<b>🔑 Выдать Premium</b>\n\n"
        "Пришли ID пользователя и количество дней в формате:\n"
        "<code>USER_ID:days</code>\n\n"
        "Например: <code>123456789:30</code>",
        reply_markup=admin_kb()
    )
    await call.answer()


@router.message(F.text.regexp(r"^\d+:\d+$"))
async def proc_admin_grant(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(":")
    user_id, days = int(parts[0]), int(parts[1])
    await db.set_user_tier(user_id, 'premium', days)
    await message.answer(f"✅ Выдан Premium пользователю {user_id} на {days} дней")


@router.message(F.text.regexp(r"^[A-Z0-9_]+:\d+$"))
async def proc_admin_promo(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(":")
    code, days = parts[0], int(parts[1])
    async with aiosqlite.connect(db.DB_PATH) as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO promo_codes (code, tier, days, uses_left) VALUES (?, 'premium', ?, 1)",
            (code, days)
        )
        await conn.commit()
    await message.answer(f"✅ Промокод <code>{code}</code> создан на {days} дней")


async def register(dp):
    dp.include_router(router)
