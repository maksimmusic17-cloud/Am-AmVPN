import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

TOKEN = "8277007634:AAFJaW4pws234-gOuC2CsbFXJZ0DLKFTo4Q"
ADMINS = [5135000311, 2032012311]

bot = Bot(token=TOKEN)
dp = Dispatcher()

conn = sqlite3.connect("bot.db")
cursor = conn.cursor()

# --- БД ---
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS keys (key TEXT PRIMARY KEY, is_used INTEGER DEFAULT 0)")
conn.commit()

# --- состояния ---
user_state = {}
active_chats = {}
pending_payments = {}

# --- МЕНЮ ---
def menu(user_id):
    buttons = [
        [InlineKeyboardButton(text="Выбрать тариф", callback_data="buy")],
        [InlineKeyboardButton(text="Скачать VPN", callback_data="download")],
        [InlineKeyboardButton(text="Поддержка", callback_data="support")]
    ]

    if user_id in ADMINS:
        buttons.append([InlineKeyboardButton(text="Админ панель", callback_data="admin")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- СТАРТ ---
@dp.message(Command("start"))
async def start(message: Message):
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?)", (message.from_user.id,))
    conn.commit()

    await message.answer("Главное меню:", reply_markup=menu(message.from_user.id))

# --- ТАРИФЫ ---
@dp.callback_query(F.data == "buy")
async def buy(call: CallbackQuery):
    await call.answer()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 месяц - 99₽", callback_data="tariff_1")],
        [InlineKeyboardButton(text="3 месяца - 299₽", callback_data="tariff_2")],
        [InlineKeyboardButton(text="1 год - 600₽", callback_data="tariff_3")],
        [InlineKeyboardButton(text="Назад", callback_data="back")]
    ])

    await call.message.edit_text("Выберите тариф:", reply_markup=kb)

# --- ВЫБОР ТАРИФА ---
@dp.callback_query(F.data.startswith("tariff_"))
async def tariff(call: CallbackQuery):
    await call.answer()

    user_id = call.from_user.id
    pending_payments[user_id] = call.data

    await call.message.answer("Отправьте скриншот оплаты")

# --- ПРИЁМ СКРИНА ---
@dp.message(F.photo)
async def payment(message: Message):
    user_id = message.from_user.id

    if user_id not in pending_payments:
        return

    for admin in ADMINS:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить", callback_data=f"ok_{user_id}")]
        ])

        await bot.send_photo(
            admin,
            message.photo[-1].file_id,
            caption=f"Оплата от {user_id}",
            reply_markup=kb
        )

    await message.answer("Ожидайте подтверждения")

# --- ПОДТВЕРЖДЕНИЕ ---
@dp.callback_query(F.data.startswith("ok_"))
async def ok(call: CallbackQuery):
    await call.answer()

    if call.from_user.id not in ADMINS:
        return

    user_id = int(call.data.split("_")[1])

    cursor.execute("SELECT key FROM keys WHERE is_used=0 LIMIT 1")
    key = cursor.fetchone()

    if key:
        cursor.execute("UPDATE keys SET is_used=1 WHERE key=?", (key[0],))
        conn.commit()
        await bot.send_message(user_id, f"Ваш ключ:\n{key[0]}")
    else:
        await bot.send_message(user_id, "Нет доступных ключей")

    await call.message.edit_caption("Подтверждено")

# --- ПОДДЕРЖКА ---
@dp.callback_query(F.data == "support")
async def support(call: CallbackQuery):
    await call.answer()

    user_id = call.from_user.id
    active_chats[user_id] = True

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Закрыть чат", callback_data="close")]
    ])

    await call.message.answer("Напишите сообщение:", reply_markup=kb)

# --- ЗАКРЫТЬ ЧАТ ---
@dp.callback_query(F.data == "close")
async def close(call: CallbackQuery):
    await call.answer()

    active_chats.pop(call.from_user.id, None)
    await call.message.answer("Чат закрыт", reply_markup=menu(call.from_user.id))

# --- ЧАТ ---
@dp.message()
async def chat(message: Message):
    user_id = message.from_user.id

    # пользователь пишет
    if user_id in active_chats and user_id not in ADMINS:
        for admin in ADMINS:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Ответить", callback_data=f"reply_{user_id}")]
            ])
            await bot.send_message(admin, f"{user_id}:\n{message.text}", reply_markup=kb)
        return

    # админ отвечает
    if user_id in user_state:
        target = user_state[user_id]
        await bot.send_message(target, f"Поддержка:\n{message.text}")
        await message.answer("Отправлено")
        user_state.pop(user_id)

# --- ОТВЕТ ---
@dp.callback_query(F.data.startswith("reply_"))
async def reply(call: CallbackQuery):
    await call.answer()

    user_id = int(call.data.split("_")[1])
    user_state[call.from_user.id] = user_id

    await call.message.answer("Введите ответ")

# --- СКАЧАТЬ ---
@dp.callback_query(F.data == "download")
async def download(call: CallbackQuery):
    await call.answer()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ПК", url="https://example.com")],
        [InlineKeyboardButton(text="Android", url="https://example.com")],
        [InlineKeyboardButton(text="Назад", callback_data="back")]
    ])

    await call.message.edit_text("Скачать VPN:", reply_markup=kb)

# --- НАЗАД ---
@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.answer()
    await call.message.edit_text("Главное меню:", reply_markup=menu(call.from_user.id))

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
