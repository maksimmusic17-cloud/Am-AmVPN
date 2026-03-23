import asyncio
import sqlite3
import aiohttp
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
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
cursor.execute("CREATE TABLE IF NOT EXISTS subs (user_id INTEGER, end_date TEXT)")
conn.commit()

# --- МЕНЮ ---
def menu(user_id):
    kb = [
        [InlineKeyboardButton(text="Личный кабинет", callback_data="profile")],
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
        "Добро пожаловать в VPN сервис",
        reply_markup=ReplyKeyboardRemove()
    )

    await message.answer("Главное меню:", reply_markup=menu(message.from_user.id))

# --- ЛИЧНЫЙ КАБИНЕТ ---
@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    await call.answer()

    cursor.execute("SELECT end_date FROM subs WHERE user_id=?", (call.from_user.id,))
    sub = cursor.fetchone()

    if sub:
        end = datetime.strptime(sub[0], "%Y-%m-%d")
        days = (end - datetime.now()).days
        text = f"Подписка активна\nОсталось дней: {days}"
    else:
        text = "Подписка не активна"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back")]
    ])

    await call.message.edit_text(text, reply_markup=kb)

# --- ТАРИФЫ ---
@dp.callback_query(F.data == "buy")
async def buy(call: CallbackQuery):
    await call.answer()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 месяц - 99₽ (1.1$)", callback_data="pay_1.1_30")],
        [InlineKeyboardButton(text="3 месяца - 299₽ (3.3$)", callback_data="pay_3.3_90")],
        [InlineKeyboardButton(text="1 год - 600₽ (6.6$)", callback_data="pay_6.6_365")],
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

    _, amount, days = call.data.split("_")
    amount = float(amount)

    invoice = await create_invoice(amount)

    pay_url = invoice["result"]["pay_url"]
    invoice_id = invoice["result"]["invoice_id"]

    cursor.execute("INSERT INTO invoices VALUES (?, ?)", (call.from_user.id, invoice_id))
    conn.commit()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить", url=pay_url)],
        [InlineKeyboardButton(text="Проверить оплату", callback_data=f"check_{invoice_id}_{days}")],
        [InlineKeyboardButton(text="Назад", callback_data="buy")]
    ])

    await call.message.edit_text("Оплатите подписку:", reply_markup=kb)

# --- ПРОВЕРКА ---
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

    _, invoice_id, days = call.data.split("_")
    data = await check_invoice(invoice_id)

    status = data["result"]["items"][0]["status"]

    if status == "paid":
        end_date = datetime.now() + timedelta(days=int(days))

        cursor.execute("DELETE FROM subs WHERE user_id=?", (call.from_user.id,))
        cursor.execute("INSERT INTO subs VALUES (?, ?)", (call.from_user.id, end_date.strftime("%Y-%m-%d")))
        conn.commit()

        await call.message.edit_text("Оплата прошла. Подписка активирована")
    else:
        await call.answer("Оплата не найдена", show_alert=True)

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
