from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app import db
from app.parsers import wildberries, ozon

router = Router()

class TrackState(StatesGroup):
    url = State()
    target = State()


def back_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅ Назад", callback_data="menu_prices")
    return kb.as_markup()


async def show_prices_menu(message, edit=False):
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Отслеживать товар", callback_data="price_add")
    kb.button(text="📋 Мои товары", callback_data="price_list")
    kb.button(text="⬅ В меню", callback_data="back_to_main")
    kb.adjust(2, 1)
    text = (
        "<b>💰 Цены</b>\n\n"
        "Отслеживание цен на Wildberries и Ozon.\n\n"
        "• <b>Отслеживать товар</b> — пришли ссылку, и я буду следить за ценой\n"
        "• <b>Мои товары</b> — список отслеживаемых позиций"
    )
    if edit:
        await message.edit_text(text, reply_markup=kb.as_markup())
    else:
        await message.answer(text, reply_markup=kb.as_markup())


@router.callback_query(F.data == "price_add")
async def cb_price_add(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "Пришли ссылку на товар (Wildberries или Ozon):\n\n"
        "<i>Например: https://www.wildberries.ru/catalog/...</i>",
        reply_markup=back_kb()
    )
    await state.set_state(TrackState.url)
    await call.answer()


@router.message(TrackState.url)
async def proc_url(message: Message, state: FSMContext):
    url = message.text.strip()
    if "wildberries.ru" in url:
        info = await wildberries.parse(url)
    elif "ozon.ru" in url:
        info = await ozon.parse(url)
    else:
        await message.answer("Поддерживаются только wildberries.ru и ozon.ru")
        return
    if not info:
        await message.answer("Не удалось получить цену. Попробуйте другую ссылку.")
        return
    await state.update_data(url=url, title=info["title"], price=info["price"], marketplace=info["marketplace"])
    await message.answer(
        f"Товар: <b>{info['title']}</b>\nЦена: {info['price']}₽\n\n"
        f"Введи желаемую цену (или 0, чтобы просто следить):",
        reply_markup=back_kb()
    )
    await state.set_state(TrackState.target)


@router.message(TrackState.target)
async def proc_target(message: Message, state: FSMContext):
    try:
        target = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введите число:")
        return
    data = await state.get_data()
    ok = await db.add_tracked_item(
        message.from_user.id, data["url"], data["title"], data["marketplace"], data["price"], target or None
    )
    await state.clear()
    if ok:
        await message.answer(
            f"✅ Добавил в отслеживание:\n<b>{data['title']}</b>\nТекущая цена: {data['price']}₽\n\n"
            f"Я буду проверять цену каждый час и сообщу, когда она снизится.",
            reply_markup=back_kb()
        )
    else:
        await message.answer("Этот товар уже отслеживается.", reply_markup=back_kb())


@router.callback_query(F.data == "price_list")
async def cb_price_list(call: CallbackQuery):
    items = await db.list_tracked_items(call.from_user.id)
    if not items:
        await call.message.edit_text(
            "Нет отслеживаемых товаров.\n\nНажми «Отслеживать товар», чтобы добавить первый.",
            reply_markup=back_kb()
        )
        await call.answer()
        return
    text = "<b>💰 Отслеживаемые товары</b>\n\n"
    for it in items:
        text += f"• <b>{it[2]}</b> — {it[4]}₽\n"
    await call.message.edit_text(text, reply_markup=back_kb())
    await call.answer()


@router.message(Command("track"))
async def cmd_track(message: Message, state: FSMContext):
    await show_prices_menu(message)


@router.message(Command("tracked"))
async def cmd_tracked(message: Message):
    items = await db.list_tracked_items(message.from_user.id)
    if not items:
        await message.answer("Нет отслеживаемых товаров.")
        return
    text = "<b>💰 Отслеживаемые товары</b>\n\n"
    for it in items:
        text += f"• <b>{it[2]}</b> — {it[4]}₽\n"
    await message.answer(text)
