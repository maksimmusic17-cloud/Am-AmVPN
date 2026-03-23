import asyncio
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties

TOKEN = "8277007634:AAFJaW4pws234-gOuC2CsbFXJZ0DLKFTo4Q"

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

ADMINS = [5135000311, 2032012311]

# --- БАЗА ---
conn = sqlite3.connect("vpn.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_value TEXT,
    is_used INTEGER DEFAULT 0,
    user_id INTEGER,
    expiry_date TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS promocodes (
    code TEXT UNIQUE,
    days INTEGER,
    uses_left INTEGER
)
""")

conn.commit()

# --- FSM ---
class AddKeys(StatesGroup):
    waiting_for_keys = State()

class AddPromo(StatesGroup):
    waiting_for_promo = State()

class EnterPromo(StatesGroup):
    waiting_for_code = State()

# --- МЕНЮ ---
def get_user_menu(user_id):
    kb = [
        [KeyboardButton(text="🔹 Купить VPN"), KeyboardButton(text="🔑 Мои ключи")],
        [KeyboardButton(text="🎟 Ввести промокод")]
    ]
    if user_id in ADMINS:
        kb.append([KeyboardButton(text="👑 Админ панель")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить ключи"), KeyboardButton(text="🎟 Добавить промокод")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🔙 Назад")]
    ],
    resize_keyboard=True
)

# --- START ---
@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("Добро пожаловать!", reply_markup=get_user_menu(message.from_user.id))

# --- АДМИН ---
@dp.message(F.text == "👑 Админ панель")
async def admin_panel(message: Message):
    if message.from_user.id in ADMINS:
        await message.answer("👑 Админ панель", reply_markup=admin_menu)

@dp.message(F.text == "🔙 Назад")
async def back(message: Message):
    await message.answer("Главное меню", reply_markup=get_user_menu(message.from_user.id))

# --- ПОКУПКА ---
@dp.message(F.text == "🔹 Купить VPN")
async def buy(message: Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="30 дней"), KeyboardButton(text="90 дней"), KeyboardButton(text="365 дней")],
            [KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )
    await message.answer("Выберите тариф:", reply_markup=kb)

# --- ВЫДАЧА КЛЮЧА ---
@dp.message(F.text.in_(["30 дней", "90 дней", "365 дней"]))
async def give_key(message: Message):
    days = int(message.text.split()[0])

    cursor.execute("SELECT * FROM keys WHERE is_used=0 LIMIT 1")
    key = cursor.fetchone()

    if key:
        expiry = datetime.now() + timedelta(days=days)

        cursor.execute(
            "UPDATE keys SET is_used=1, user_id=?, expiry_date=? WHERE id=?",
            (message.from_user.id, expiry.strftime("%Y-%m-%d"), key[0])
        )
        conn.commit()

        await message.answer(
            f"✅ Ключ:\n{key[1]}\n⏳ До: {expiry.strftime('%Y-%m-%d')}",
            reply_markup=get_user_menu(message.from_user.id)
        )
    else:
        await message.answer("❌ Нет ключей")

# --- МОИ КЛЮЧИ ---
@dp.message(F.text == "🔑 Мои ключи")
async def my_keys(message: Message):
    cursor.execute("SELECT key_value, expiry_date FROM keys WHERE user_id=?", (message.from_user.id,))
    keys = cursor.fetchall()

    if keys:
        text = "\n\n".join([f"{k[0]}\n⏳ До: {k[1]}" for k in keys])
        await message.answer(text)
    else:
        await message.answer("Нет ключей")

# --- ПРОМОКОД ВВОД ---
@dp.message(F.text == "🎟 Ввести промокод")
async def promo(message: Message, state: FSMContext):
    await state.set_state(EnterPromo.waiting_for_code)
    await message.answer("Введите промокод:")

@dp.message(EnterPromo.waiting_for_code)
async def apply_promo(message: Message, state: FSMContext):
    cursor.execute("SELECT days, uses_left FROM promocodes WHERE code=?", (message.text,))
    promo = cursor.fetchone()

    if promo and promo[1] > 0:
        days = promo[0]

        cursor.execute("SELECT id, expiry_date FROM keys WHERE user_id=?", (message.from_user.id,))
        keys = cursor.fetchall()

        for k in keys:
            expiry = datetime.strptime(k[1], "%Y-%m-%d")
            new_expiry = expiry + timedelta(days=days)

            cursor.execute("UPDATE keys SET expiry_date=? WHERE id=?", (new_expiry.strftime("%Y-%m-%d"), k[0]))

        cursor.execute("UPDATE promocodes SET uses_left=uses_left-1 WHERE code=?", (message.text,))
        conn.commit()

        await message.answer(f"✅ Добавлено {days} дней!")
    else:
        await message.answer("❌ Неверный или использован")

    await state.clear()

# --- ДОБАВИТЬ КЛЮЧИ ---
@dp.message(F.text == "➕ Добавить ключи")
async def add_keys(message: Message, state: FSMContext):
    if message.from_user.id in ADMINS:
        await state.set_state(AddKeys.waiting_for_keys)
        await message.answer("Вставь ключи:")

@dp.message(AddKeys.waiting_for_keys)
async def save_keys(message: Message, state: FSMContext):
    for k in message.text.split("\n"):
        cursor.execute("INSERT INTO keys (key_value) VALUES (?)", (k,))
    conn.commit()
    await message.answer("Готово")
    await state.clear()

# --- ПРОМОКОДЫ ---
@dp.message(F.text == "🎟 Добавить промокод")
async def add_promo(message: Message, state: FSMContext):
    if message.from_user.id in ADMINS:
        await state.set_state(AddPromo.waiting_for_promo)
        await message.answer("Формат: CODE DAYS USES\nпример: FREE30 30 5")

@dp.message(AddPromo.waiting_for_promo)
async def save_promo(message: Message, state: FSMContext):
    try:
        code, days, uses = message.text.split()

        cursor.execute("SELECT * FROM promocodes WHERE code=?", (code,))
        if cursor.fetchone():
            await message.answer("❌ Такой промокод уже есть")
        else:
            cursor.execute("INSERT INTO promocodes VALUES (?, ?, ?)", (code, int(days), int(uses)))
            conn.commit()
            await message.answer("✅ Добавлен")
    except:
        await message.answer("❌ Ошибка")

    await state.clear()

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())