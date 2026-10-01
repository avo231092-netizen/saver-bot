from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from app import db

router = Router()

class AddSubState(StatesGroup):
    name = State()
    cost = State()
    date = State()
    cycle = State()


def back_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅ Назад", callback_data="menu_subs")
    return kb.as_markup()


async def show_subscriptions_menu(message, edit=False):
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить подписку", callback_data="sub_add")
    kb.button(text="📋 Список", callback_data="sub_list")
    kb.button(text="❌ Отменить", callback_data="sub_cancel")
    kb.button(text="⬅ В меню", callback_data="back_to_main")
    kb.adjust(2, 2)
    text = (
        "<b>📋 Подписки</b>\n\n"
        "Здесь ты можешь управлять своими подписками.\n\n"
        "• <b>Добавить</b> — внести новую подписку\n"
        "• <b>Список</b> — посмотреть все активные\n"
        "• <b>Отменить</b> — убрать ненужную"
    )
    if edit:
        await message.edit_text(text, reply_markup=kb.as_markup())
    else:
        await message.answer(text, reply_markup=kb.as_markup())


@router.callback_query(F.data == "sub_add")
async def cb_sub_add(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "Введи название подписки:\n\n<i>Например: Netflix, Spotify, iCloud, спортзал</i>",
        reply_markup=back_kb()
    )
    await state.set_state(AddSubState.name)
    await call.answer()


@router.message(AddSubState.name)
async def proc_sub_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Стоимость в месяц (число, ₽):", reply_markup=back_kb())
    await state.set_state(AddSubState.cost)


@router.message(AddSubState.cost)
async def proc_sub_cost(message: Message, state: FSMContext):
    try:
        cost = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введите число:")
        return
    await state.update_data(cost=cost)
    await message.answer(
        "Дата следующего списания (ГГГГ-ММ-ДД):\n<i>Например: 2026-10-15</i>",
        reply_markup=back_kb()
    )
    await state.set_state(AddSubState.date)


@router.message(AddSubState.date)
async def proc_sub_date(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%Y-%m-%d")
    except ValueError:
        await message.answer("Формат: ГГГГ-ММ-ДД")
        return
    await state.update_data(next_payment=message.text)
    kb = InlineKeyboardBuilder()
    kb.button(text="Ежемесячно", callback_data="cycle_monthly")
    kb.button(text="Ежегодно", callback_data="cycle_yearly")
    kb.button(text="Разово", callback_data="cycle_once")
    kb.button(text="⬅ Назад", callback_data="menu_subs")
    kb.adjust(2, 1, 1)
    await message.answer("Периодичность:", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("cycle_"))
async def proc_cycle(call: CallbackQuery, state: FSMContext):
    cycle = call.data.split("_", 1)[1]
    data = await state.get_data()
    await db.add_subscription(
        call.from_user.id, data["name"], data["cost"], data["next_payment"], cycle
    )
    await state.clear()
    await call.message.edit_text(
        f"✅ Подписка добавлена:\n<b>{data['name']}</b> — {data['cost']}₽\nСписание: {data['next_payment']}",
        reply_markup=back_kb()
    )
    await call.answer()


@router.callback_query(F.data == "sub_list")
async def cb_sub_list(call: CallbackQuery):
    subs = await db.list_subscriptions(call.from_user.id)
    if not subs:
        await call.message.edit_text(
            "У тебя пока нет подписок.\n\nНажми «Добавить», чтобы внести первую.",
            reply_markup=back_kb()
        )
        await call.answer()
        return
    text = "<b>📋 Твои подписки</b>\n\n"
    for s in subs:
        text += f"• <b>{s[1]}</b> — {s[2]}₽, списание {s[5]}\n"
    await call.message.edit_text(text, reply_markup=back_kb())
    await call.answer()


@router.callback_query(F.data == "sub_cancel")
async def cb_sub_cancel(call: CallbackQuery):
    subs = await db.list_subscriptions(call.from_user.id)
    if not subs:
        await call.message.edit_text("Нечего отменять.", reply_markup=back_kb())
        await call.answer()
        return
    kb = InlineKeyboardBuilder()
    for s in subs:
        kb.button(text=f"{s[1]} ({s[2]}₽)", callback_data=f"cancel_{s[0]}")
    kb.button(text="⬅ Назад", callback_data="menu_subs")
    kb.adjust(1)
    await call.message.edit_text("Что отменить?", reply_markup=kb.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("cancel_"))
async def proc_cancel(call: CallbackQuery):
    sub_id = int(call.data.split("_", 1)[1])
    await db.cancel_subscription(call.from_user.id, sub_id)
    await call.message.edit_text("✅ Отменено.", reply_markup=back_kb())
    await call.answer()


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    await show_subscriptions_menu(message)


@router.message(Command("list"))
async def cmd_list(message: Message):
    subs = await db.list_subscriptions(message.from_user.id)
    if not subs:
        await message.answer("Подписок нет.")
        return
    text = "<b>📋 Подписки</b>\n\n"
    for s in subs:
        text += f"• <b>{s[1]}</b> — {s[2]}₽, списание {s[5]}\n"
    await message.answer(text)
