import asyncio
import logging
import sqlite3
import aiohttp
from datetime import datetime, timedelta

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

# ---------- БД ----------
conn = sqlite3.connect("bot.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    sub_until TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS payments (
    user_id INTEGER,
    invoice_id INTEGER,
    days INTEGER
)
""")

conn.commit()

# ---------- UI ----------
def main_menu(user_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="Личный кабинет", callback_data="profile")
    kb.button(text="Выбрать тариф", callback_data="tariffs")
    kb.button(text="Поддержка", callback_data="support")
    if user_id in ADMINS:
        kb.button(text="Админ панель", callback_data="admin")
    kb.adjust(1)
    return kb.as_markup()

def tariffs_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="1 месяц - 99₽ (1.1$)", callback_data="buy_30")
    kb.button(text="3 месяца - 299₽ (3.3$)", callback_data="buy_90")
    kb.button(text="1 год - 600₽ (6.6$)", callback_data="buy_365")
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

# ---------- Crypto ----------
async def create_invoice(amount):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    data = {"asset": "USDT", "amount": amount}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers=headers) as resp:
            return (await resp.json())["result"]

async def check_invoice(invoice_id):
    url = f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            return (await resp.json())["result"]["items"][0]["status"]

# ---------- START ----------
@dp.message(Command("start"))
async def start(message: Message):
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?)", (message.from_user.id, None))
    conn.commit()

    photo = FSInputFile("logo.jpg")

    await message.answer_photo(
        photo=photo,
        caption="Добро пожаловать в VPN сервис\n\nГлавное меню:",
        reply_markup=main_menu(message.from_user.id)
    )

# ---------- PROFILE ----------
@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    await call.answer()

    cursor.execute("SELECT sub_until FROM users WHERE user_id=?", (call.from_user.id,))
    sub = cursor.fetchone()[0]

    text = f"Подписка до: {sub}" if sub else "У вас нет активной подписки"

    await call.message.edit_caption(
        caption=text,
        reply_markup=main_menu(call.from_user.id)
    )

# ---------- TARIFFS ----------
@dp.callback_query(F.data == "tariffs")
async def tariffs(call: CallbackQuery):
    await call.answer()
    await call.message.edit_caption(
        caption="Выберите тариф:",
        reply_markup=tariffs_kb()
    )

# ---------- BUY ----------
@dp.callback_query(F.data.startswith("buy_"))
async def buy(call: CallbackQuery):
    await call.answer()

    plans = {
        "buy_30": (1.1, 30),
        "buy_90": (3.3, 90),
        "buy_365": (6.6, 365)
    }

    amount, days = plans[call.data]
    invoice = await create_invoice(amount)

    cursor.execute("INSERT INTO payments VALUES (?, ?, ?)",
                   (call.from_user.id, invoice["invoice_id"], days))
    conn.commit()

    await call.message.edit_caption(
        caption="Оплатите подписку:",
        reply_markup=payment_kb(invoice["pay_url"])
    )

# ---------- CHECK ----------
@dp.callback_query(F.data == "check")
async def check(call: CallbackQuery):
    await call.answer()

    cursor.execute("SELECT invoice_id, days FROM payments WHERE user_id=? ORDER BY rowid DESC",
                   (call.from_user.id,))
    row = cursor.fetchone()

    if not row:
        await call.answer("Нет оплаты", show_alert=True)
        return

    invoice_id, days = row
    status = await check_invoice(invoice_id)

    if status == "paid":
        new_date = datetime.now() + timedelta(days=days)

        cursor.execute("UPDATE users SET sub_until=? WHERE user_id=?",
                       (new_date.strftime("%Y-%m-%d"), call.from_user.id))
        conn.commit()

        await call.message.edit_caption(
            caption=f"Оплата прошла!\nПодписка до: {new_date.strftime('%Y-%m-%d')}",
            reply_markup=main_menu(call.from_user.id)
        )
    else:
        await call.answer("Оплата не найдена", show_alert=True)

# ---------- BACK ----------
@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.answer()
    await call.message.edit_caption(
        caption="Главное меню:",
        reply_markup=main_menu(call.from_user.id)
    )

# ---------- SUPPORT ----------
support_mode = {}

@dp.callback_query(F.data == "support")
async def support(call: CallbackQuery):
    await call.answer()
    support_mode[call.from_user.id] = True

    await call.message.edit_caption(
        caption="Напишите сообщение в поддержку:"
    )

@dp.message()
async def support_msg(message: Message):
    if message.from_user.id in support_mode:
        for admin in ADMINS:
            await bot.send_message(admin, f"Обращение от {message.from_user.id}:\n{message.text}")
        await message.answer("Отправлено")
        support_mode.pop(message.from_user.id)

# ---------- RUN ----------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
