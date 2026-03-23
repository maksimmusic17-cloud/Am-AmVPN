import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

TOKEN = "ТВОЙ_ТОКЕН_СЮДА"
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
active_chats = {}  # user_id -> True

# --- МЕНЮ ---
def main_menu(user_id):
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

    await message.answer("Главное меню:", reply_markup=main_menu(message.from_user.id))

# --- ПОДДЕРЖКА СТАРТ ---
@dp.callback_query(F.data == "support")
async def support(call: CallbackQuery):
    user_id = call.from_user.id
    active_chats[user_id] = True

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Закрыть чат", callback_data="close_chat")]
    ])

    await call.message.answer(
        "Чат с поддержкой открыт. Напишите сообщение.",
        reply_markup=kb
    )

# --- ЗАКРЫТЬ ЧАТ ---
@dp.callback_query(F.data == "close_chat")
async def close_chat(call: CallbackQuery):
    user_id = call.from_user.id

    if user_id in active_chats:
        active_chats.pop(user_id)

    await call.message.answer("Чат закрыт", reply_markup=main_menu(user_id))

# --- ПЕРЕСЫЛКА СООБЩЕНИЙ ---
@dp.message()
async def chat_handler(message: Message):
    user_id = message.from_user.id

    # пользователь пишет в поддержку
    if user_id in active_chats and user_id not in ADMINS:
        for admin in ADMINS:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Ответить", callback_data=f"reply_{user_id}")]
            ])

            await bot.send_message(
                admin,
                f"Сообщение от {user_id}:\n{message.text}",
                reply_markup=kb
            )

        return

    # админ отвечает
    state = user_state.get(user_id)

    if isinstance(state, tuple) and state[0] == "reply":
        target_user = state[1]

        await bot.send_message(target_user, f"Поддержка:\n{message.text}")
        await message.answer("Ответ отправлен")

        user_state.pop(user_id)

# --- КНОПКА ОТВЕТИТЬ ---
@dp.callback_query(F.data.startswith("reply_"))
async def reply(call: CallbackQuery):
    if call.from_user.id not in ADMINS:
        return

    user_id = int(call.data.split("_")[1])
    user_state[call.from_user.id] = ("reply", user_id)

    await call.message.answer(f"Введите ответ для {user_id}:")

# --- СКАЧАТЬ VPN ---
@dp.callback_query(F.data == "download")
async def download(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Для ПК", url="https://example.com")],
        [InlineKeyboardButton(text="Для Android", url="https://example.com")],
        [InlineKeyboardButton(text="Назад", callback_data="back")]
    ])
    await call.message.edit_text("Скачать VPN:", reply_markup=kb)

# --- НАЗАД ---
@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text("Главное меню:", reply_markup=main_menu(call.from_user.id))

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
