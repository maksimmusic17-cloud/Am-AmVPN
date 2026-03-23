import asyncio
import sqlite3
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

TOKEN = "8277007634:AAFJaW4pws234-gOuC2CsbFXJZ0DLKFTo4Q"
CRYPTO_TOKEN = "555209:AAvWWWiQt0ERfGAjTGozQDu1HEAZICFi4ZW"
ADMINS = [5135000311, 2032012311]

bot = Bot(token=TOKEN)
dp = Dispatcher()

conn = sqlite3.connect("bot.db")
cursor = conn.cursor()

# --- БД ---
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS keys (key TEXT PRIMARY KEY, is_used INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS invoices (user_id INTEGER, invoice_id TEXT)")
conn.commit()

# --- UI ---
def menu(user_id):
    kb = [
        [InlineKeyboardButton(text="Выбрать тариф", callback_data="buy")],
        [InlineKeyboardButton(text="Скачать VPN", callback_data="download")],
        [InlineKeyboardButton(text="Поддержка", callback_data="support")]
    ]

    if user_id in ADMINS:
        kb.append([InlineKeyboardButton(text="Админ панель", callback_data="admin")])

    return InlineKeyboardMarkup(inline_keyboard=kb)

# --- СТАРТ ---
@dp.message(Command("start"))
async def start(message: Message):
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?)", (message.from_user.id,))
    conn.commit()

    await message.answer(
        "Добро пожаловать в VPN сервис\n\nВыберите действие:",
        reply_markup=menu(message.from_user.id)
    )

# --- ТАРИФЫ ---
@dp.callback_query(F.data == "buy")
async def buy(call: CallbackQuery):
    await call.answer()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 месяц - 99₽ (1.1$)", callback_data="pay_1.1")],
        [InlineKeyboardButton(text="3 месяца - 299₽ (3.3$)", callback_data="pay_3.3")],
        [InlineKeyboardButton(text="1 год - 600₽ (6.6$)", callback_data="pay_6.6")],
        [InlineKeyboardButton(text="Назад", callback_data="back")]
    ])

    await call.message.edit_text("Выберите тариф:", reply_markup=kb)

# --- СОЗДАНИЕ ИНВОЙСА ---
async def create_invoice(amount):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    data = {
        "asset": "USDT",
        "amount": amount,
        "description": "VPN подписка"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as resp:
            return await resp.json()

# --- ОПЛАТА ---
@dp.callback_query(F.data.startswith("pay_"))
async def pay(call: CallbackQuery):
    await call.answer()

    user_id = call.from_user.id
    amount = float(call.data.split("_")[1])

    invoice = await create_invoice(amount)

    pay_url = invoice["result"]["pay_url"]
    invoice_id = invoice["result"]["invoice_id"]

    cursor.execute("INSERT INTO invoices VALUES (?, ?)", (user_id, invoice_id))
    conn.commit()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить", url=pay_url)],
        [InlineKeyboardButton(text="Проверить оплату", callback_data=f"check_{invoice_id}")]
    ])

    await call.message.answer("Оплатите подписку:", reply_markup=kb)

# --- ПРОВЕРКА ОПЛАТЫ ---
async def check_invoice(invoice_id):
    url = f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            return await resp.json()

# --- ПРОВЕРИТЬ ---
@dp.callback_query(F.data.startswith("check_"))
async def check(call: CallbackQuery):
    await call.answer()

    invoice_id = call.data.split("_")[1]
    data = await check_invoice(invoice_id)

    status = data["result"]["items"][0]["status"]

    if status == "paid":
        cursor.execute("SELECT user_id FROM invoices WHERE invoice_id=?", (invoice_id,))
        user_id = cursor.fetchone()[0]

        cursor.execute("SELECT key FROM keys WHERE is_used=0 LIMIT 1")
        key = cursor.fetchone()

        if key:
            cursor.execute("UPDATE keys SET is_used=1 WHERE key=?", (key[0],))
            conn.commit()

            await bot.send_message(user_id, f"Оплата прошла\n\nВаш ключ:\n{key[0]}")
        else:
            await bot.send_message(user_id, "Нет доступных ключей, напишите в поддержку")

        await call.message.edit_text("Оплачено")
    else:
        await call.message.answer("Оплата не найдена")

# --- АДМИНКА ---
@dp.callback_query(F.data == "admin")
async def admin(call: CallbackQuery):
    await call.answer()

    if call.from_user.id not in ADMINS:
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить ключ", callback_data="add_key")],
        [InlineKeyboardButton(text="Список пользователей", callback_data="users")],
        [InlineKeyboardButton(text="Назад", callback_data="back")]
    ])

    await call.message.edit_text("Админ панель:", reply_markup=kb)

# --- ДОБАВИТЬ КЛЮЧ ---
@dp.callback_query(F.data == "add_key")
async def add_key(call: CallbackQuery):
    await call.answer()
    await call.message.answer("Отправь ключ")
    dp.message.register(save_key)

async def save_key(message: Message):
    cursor.execute("INSERT INTO keys VALUES (?, 0)", (message.text,))
    conn.commit()
    await message.answer("Ключ добавлен")

# --- ПОЛЬЗОВАТЕЛИ ---
@dp.callback_query(F.data == "users")
async def users(call: CallbackQuery):
    await call.answer()

    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()

    text = "\n".join([str(u[0]) for u in users]) or "Нет пользователей"

    await call.message.answer(f"Список пользователей:\n{text}")

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

# --- ПОДДЕРЖКА ---
active_chats = {}
user_state = {}

@dp.callback_query(F.data == "support")
async def support(call: CallbackQuery):
    await call.answer()

    active_chats[call.from_user.id] = True

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Закрыть чат", callback_data="close_chat")]
    ])

    await call.message.answer("Напишите сообщение:", reply_markup=kb)

@dp.callback_query(F.data == "close_chat")
async def close_chat(call: CallbackQuery):
    await call.answer()
    active_chats.pop(call.from_user.id, None)
    await call.message.answer("Чат закрыт", reply_markup=menu(call.from_user.id))

@dp.message()
async def chat(message: Message):
    user_id = message.from_user.id

    if user_id in active_chats and user_id not in ADMINS:
        for admin in ADMINS:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Ответить", callback_data=f"reply_{user_id}")]
            ])
            await bot.send_message(admin, f"{user_id}:\n{message.text}", reply_markup=kb)
        return

    if user_id in user_state:
        target = user_state[user_id]
        await bot.send_message(target, f"Поддержка:\n{message.text}")
        await message.answer("Ответ отправлен")
        user_state.pop(user_id)

@dp.callback_query(F.data.startswith("reply_"))
async def reply(call: CallbackQuery):
    await call.answer()

    user_id = int(call.data.split("_")[1])
    user_state[call.from_user.id] = user_id

    await call.message.answer("Введите ответ")

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
