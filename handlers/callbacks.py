from aiogram import types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
from config import dp, bot, CHANNEL_ID_GASTRO_PETER, CHANNEL_ID_SMALL_PETER
from config import CHANNEL_USERNAME_GASTRO_PETER, CHANNEL_USERNAME_SMALL_PETER
from config import GASTRO_GUIDE_FILE_ID, SMALL_PETER_FILE_ID
from messages import ALREADY_SUBSCRIBED_GASTRO, ALREADY_SUBSCRIBED_SMALL, NOT_SUBSCRIBED_PROMPT

async def process_gastro_guide(call: types.CallbackQuery):
    user_id = call.from_user.id
    # Попробуем проверить через username — обычно надёжнее для публичных каналов
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME_GASTRO_PETER, user_id)
        if member.status in ("member", "administrator", "creator"):
            await bot.send_document(user_id, GASTRO_GUIDE_FILE_ID, caption=ALREADY_SUBSCRIBED_GASTRO)
            await call.answer()
            return
        # Если статус left/kicked или другой — считаем не подписанным
    except TelegramBadRequest as e:
        # Telegram может вернуть "member list is inaccessible" для каналов
        print(f"Ошибка при проверке подписки (gastro): {e}")
    except Exception as e:
        print(f"Неожиданная ошибка при проверке подписки (gastro): {e}")

    # Фоллбек: показываем пользователю ссылку на канал и кнопку для повторной проверки
    open_btn = InlineKeyboardButton(text="Открыть канал", url=f"https://t.me/{CHANNEL_USERNAME_GASTRO_PETER.lstrip('@')}")
    check_btn = InlineKeyboardButton(text="Я подписался — проверить", callback_data="check_gastro")
    kb = InlineKeyboardMarkup(inline_keyboard=[[open_btn], [check_btn]])
    await call.message.answer(NOT_SUBSCRIBED_PROMPT.format(channel_name=CHANNEL_USERNAME_GASTRO_PETER), reply_markup=kb)
    await call.answer()

async def process_spb_guide(call: types.CallbackQuery):
    user_id = call.from_user.id
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME_SMALL_PETER, user_id)
        if member.status in ("member", "administrator", "creator"):
            await bot.send_document(user_id, SMALL_PETER_FILE_ID, caption=ALREADY_SUBSCRIBED_SMALL)
            await call.answer()
            return
    except TelegramBadRequest as e:
        print(f"Ошибка при проверке подписки (spb): {e}")
    except Exception as e:
        print(f"Неожиданная ошибка при проверке подписки (spb): {e}")

    open_btn = InlineKeyboardButton(text="Открыть канал", url=f"https://t.me/{CHANNEL_USERNAME_SMALL_PETER.lstrip('@')}")
    check_btn = InlineKeyboardButton(text="Я подписался — проверить", callback_data="check_spb")
    kb = InlineKeyboardMarkup(inline_keyboard=[[open_btn], [check_btn]])
    await call.message.answer(NOT_SUBSCRIBED_PROMPT.format(channel_name=CHANNEL_USERNAME_SMALL_PETER), reply_markup=kb)
    await call.answer()

# ✅ Регистрация обработчиков для callback-запросов с использованием F.data вместо лямбда
dp.callback_query.register(process_gastro_guide, F.data == "guide_gastro")
dp.callback_query.register(process_spb_guide, F.data == "guide_spb")


async def check_gastro_callback(call: types.CallbackQuery):
    """Callback when user pressed "Я подписался — проверить" for gastro channel."""
    user_id = call.from_user.id
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME_GASTRO_PETER, user_id)
        if member.status in ("member", "administrator", "creator"):
            await bot.send_document(user_id, GASTRO_GUIDE_FILE_ID, caption=ALREADY_SUBSCRIBED_GASTRO)
        else:
            await call.message.answer(NOT_SUBSCRIBED_PROMPT.format(channel_name=CHANNEL_USERNAME_GASTRO_PETER))
    except TelegramBadRequest as e:
        print(f"Re-check error (gastro): {e}")
        await call.message.answer(NOT_SUBSCRIBED_PROMPT.format(channel_name=CHANNEL_USERNAME_GASTRO_PETER))
    except Exception as e:
        print(f"Unexpected re-check error (gastro): {e}")
        await call.message.answer(NOT_SUBSCRIBED_PROMPT.format(channel_name=CHANNEL_USERNAME_GASTRO_PETER))
    await call.answer()


async def check_spb_callback(call: types.CallbackQuery):
    """Callback when user pressed "Я подписался — проверить" for small peter channel."""
    user_id = call.from_user.id
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME_SMALL_PETER, user_id)
        if member.status in ("member", "administrator", "creator"):
            await bot.send_document(user_id, SMALL_PETER_FILE_ID, caption=ALREADY_SUBSCRIBED_SMALL)
        else:
            await call.message.answer(NOT_SUBSCRIBED_PROMPT.format(channel_name=CHANNEL_USERNAME_SMALL_PETER))
    except TelegramBadRequest as e:
        print(f"Re-check error (spb): {e}")
        await call.message.answer(NOT_SUBSCRIBED_PROMPT.format(channel_name=CHANNEL_USERNAME_SMALL_PETER))
    except Exception as e:
        print(f"Unexpected re-check error (spb): {e}")
        await call.message.answer(NOT_SUBSCRIBED_PROMPT.format(channel_name=CHANNEL_USERNAME_SMALL_PETER))
    await call.answer()


dp.callback_query.register(check_gastro_callback, F.data == "check_gastro")
dp.callback_query.register(check_spb_callback, F.data == "check_spb")