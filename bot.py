import asyncio
import logging
import sqlite3
import aiohttp

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

TOKEN = "8277007634:AAFJaW4pws234-gOuC2CsbFXJZ0DLKFTo4Q"
CRYPTO_TOKEN = "555209:AAvWWWiQt0ERfGAjTGozQDu1HEAZICFi4ZW"
ADMINS = [5135000311, 2032012311]

bot = Bot(token=TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

conn = sqlite3.connect("bot.db")
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS payments (user_id INTEGER, invoice_id INTEGER)")
conn.commit()

# ---------- UI ----------
def main_menu(user_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="Выбрать тариф", callback_data="tariffs")
    kb.button(text="Поддержка", callback_data="support")
    if user_id in ADMINS:
        kb.button(text="Админ панель", callback_data="admin")
    kb.adjust(1)
    return kb.as_markup()

def tariffs_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="1 месяц - 99₽ (1.1$)", callback_data="buy_1")
    kb.button(text="3 месяца - 299₽ (3.3$)", callback_data="buy_3")
    kb.button(text="1 год - 600₽ (6.6$)", callback_data="buy_12")
    kb.button(text="Назад", callback_data="back")
    kb.adjust(1)
    return kb.as_markup()

def payment_kb(url):
    kb = InlineKeyboardBuilder()
    kb.button(text="Оплатить", url=url)
    kb.button(text="Проверить оплату", callback_data="check")
    kb.button(text="Назад", callback_data="tariffs")
    kb.adjust(1)
    return kb.as_markup()

# ---------- CryptoBot ----------
async def create_invoice(amount):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    data = {
        "asset": "USDT",
        "amount": amount
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers=headers) as resp:
            res = await resp.json()
            return res["result"]

async def check_invoice(invoice_id):
    url = f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            res = await resp.json()
            return res["result"]["items"][0]["status"]

# ---------- START ----------
@dp.message(Command("start"))
async def start(message: Message):
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?)", (message.from_user.id,))
    conn.commit()

    photo = FSInputFile("logo.jpg")

    await message.answer_photo(
        photo=photo,
        caption="Главное меню",
        reply_markup=main_menu(message.from_user.id)
    )

# ---------- ТАРИФЫ ----------
@dp.callback_query(F.data == "tariffs")
async def tariffs(call: CallbackQuery):
    await call.message.edit_text("Выберите тариф:", reply_markup=tariffs_kb())

@dp.callback_query(F.data.startswith("buy_"))
async def buy(call: CallbackQuery):
    plans = {
        "buy_1": 1.1,
        "buy_3": 3.3,
        "buy_12": 6.6
    }

    amount = plans[call.data]

    invoice = await create_invoice(amount)

    invoice_id = invoice["invoice_id"]
    pay_url = invoice["pay_url"]

    cursor.execute("INSERT INTO payments VALUES (?, ?)", (call.from_user.id, invoice_id))
    conn.commit()

    await call.message.edit_text(
        "Оплатите подписку:",
        reply_markup=payment_kb(pay_url)
    )

# ---------- ПРОВЕРКА ----------
@dp.callback_query(F.data == "check")
async def check(call: CallbackQuery):
    cursor.execute("SELECT invoice_id FROM payments WHERE user_id=?", (call.from_user.id,))
    row = cursor.fetchone()

    if not row:
        await call.answer("Нет оплаты", show_alert=True)
        return

    status = await check_invoice(row[0])

    if status == "paid":
        await call.message.edit_text("Оплата прошла! Ваш VPN ключ:\nABC-123-XYZ")
    else:
        await call.answer("Оплата не найдена", show_alert=True)

# ---------- ЗАПУСК ----------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
