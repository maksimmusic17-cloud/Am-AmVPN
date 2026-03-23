import asyncio
import logging
import aiohttp
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

# --- НАСТРОЙКИ ---
TOKEN = "8277007634:AAFJaW4pws234-gOuC2CsbFXJZ0DLKFTo4Q"
CRYPTO_TOKEN = "555209:AAvWWWiQt0ERfGAjTGozQDu1HEAZICFi4ZW"

ADMINS = [2032012311]

# --- БОТ ---
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БАЗА ---
users = {}
waiting_support = set()

# --- ТВОЯ КАРТИНКА ---
PHOTO_URL = "https://i.ibb.co/7nQxK7T/am-am-vpn.png"  # твоя картинка

# --- КНОПКИ ---
def main_menu(user_id):
    buttons = [
        [InlineKeyboardButton(text="Личный кабинет", callback_data="profile")],
        [InlineKeyboardButton(text="Выбрать тариф", callback_data="tariffs")],
        [InlineKeyboardButton(text="Скачать VPN", callback_data="download")],
        [InlineKeyboardButton(text="Поддержка", callback_data="support")]
    ]

    if user_id in ADMINS:
        buttons.append([InlineKeyboardButton(text="Админ панель", callback_data="admin")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# --- СТАРТ ---
@dp.message(CommandStart())
async def start(msg: types.Message):
    if msg.from_user.id not in users:
        users[msg.from_user.id] = {
            "sub": False,
            "reg_date": datetime.now().strftime("%d.%m.%Y")
        }

    await msg.answer_photo(
        photo=PHOTO_URL,
        caption="Добро пожаловать в Am-Am VPN\n\nГлавное меню:",
        reply_markup=main_menu(msg.from_user.id)
    )


# --- CALLBACK ---
@dp.callback_query()
async def handler(call: types.CallbackQuery):
    user_id = call.from_user.id

    # --- ПРОФИЛЬ ---
    if call.data == "profile":
        user = users[user_id]

        text = (
            "Личный кабинет\n\n"
            f"ID: {user_id}\n"
            f"Дата регистрации: {user['reg_date']}\n"
            f"Подписка: {'АКТИВНА' if user['sub'] else 'НЕТ'}"
        )

        await call.message.edit_caption(text, reply_markup=main_menu(user_id))

    # --- ТАРИФЫ ---
    elif call.data == "tariffs":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1 месяц - 99₽ (1.1$)", callback_data="buy_1")],
            [InlineKeyboardButton(text="3 месяца - 299₽ (3.3$)", callback_data="buy_3")],
            [InlineKeyboardButton(text="1 год - 600₽ (6.6$)", callback_data="buy_12")],
            [InlineKeyboardButton(text="Назад", callback_data="back")]
        ])

        await call.message.edit_caption("Выберите тариф:", reply_markup=kb)

    # --- ОПЛАТА ---
    elif call.data.startswith("buy_"):
        prices = {"buy_1": 1.1, "buy_3": 3.3, "buy_12": 6.6}
        amount = prices[call.data]

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://pay.crypt.bot/api/createInvoice",
                headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
                json={"asset": "USDT", "amount": amount}
            ) as resp:
                data = await resp.json()

        pay_url = data["result"]["pay_url"]

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить", url=pay_url)],
            [InlineKeyboardButton(text="Проверить оплату", callback_data="check")],
            [InlineKeyboardButton(text="Назад", callback_data="tariffs")]
        ])

        await call.message.edit_caption("Оплатите подписку:", reply_markup=kb)

    elif call.data == "check":
        users[user_id]["sub"] = True

        await call.message.edit_caption(
            "Оплата подтверждена\n\nВаш ключ:\nABC-123-XYZ",
            reply_markup=main_menu(user_id)
        )

    # --- СКАЧАТЬ ---
    elif call.data == "download":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="ПК", url="https://example.com")],
            [InlineKeyboardButton(text="Android", url="https://example.com")],
            [InlineKeyboardButton(text="Назад", callback_data="back")]
        ])

        await call.message.edit_caption("Скачать VPN:", reply_markup=kb)

    # --- ПОДДЕРЖКА ---
    elif call.data == "support":
        waiting_support.add(user_id)

        await call.message.edit_caption(
            "Напишите сообщение для поддержки",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="back")]]
            )
        )

    # --- АДМИН ПАНЕЛЬ ---
    elif call.data == "admin" and user_id in ADMINS:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Статистика", callback_data="stats")],
            [InlineKeyboardButton(text="Назад", callback_data="back")]
        ])

        await call.message.edit_caption("Админ панель", reply_markup=kb)

    # --- СТАТИСТИКА ---
    elif call.data == "stats" and user_id in ADMINS:
        total = len(users)
        active = sum(1 for u in users.values() if u["sub"])

        text = (
            "Статистика\n\n"
            f"Всего пользователей: {total}\n"
            f"Активных подписок: {active}\n"
            f"Без подписки: {total - active}"
        )

        await call.message.edit_caption(
            text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin")]]
            )
        )

    # --- НАЗАД ---
    elif call.data == "back":
        await call.message.edit_caption("Главное меню:", reply_markup=main_menu(user_id))

    await call.answer()


# --- ПОДДЕРЖКА ---
@dp.message()
async def support(msg: types.Message):
    user_id = msg.from_user.id

    if user_id in waiting_support:
        for admin in ADMINS:
            await bot.send_message(admin, f"Обращение от {user_id}:\n{msg.text}")

        await msg.answer("Сообщение отправлено")
        waiting_support.remove(user_id)
        return


# --- ЗАПУСК ---
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
