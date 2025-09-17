from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import dp, bot, CHANNEL_ID_GASTRO_PETER, CHANNEL_ID_SMALL_PETER
from config import CHANNEL_USERNAME_GASTRO_PETER, CHANNEL_USERNAME_SMALL_PETER
from config import GASTRO_GUIDE_FILE_ID, SMALL_PETER_FILE_ID
from messages import ALREADY_SUBSCRIBED_GASTRO, ALREADY_SUBSCRIBED_SMALL, NOT_SUBSCRIBED_PROMPT

@dp.callback_query_handler(lambda call: call.data == "guide_gastro")
async def process_gastro_guide(call: types.CallbackQuery):
    """Handles the inline button for 'Гайд гастропутешествия'."""
    user_id = call.from_user.id
    # Check subscription status for the gastro guide channel
    is_member = False
    try:
        member = await bot.get_chat_member(CHANNEL_ID_GASTRO_PETER, user_id)
        # Consider subscribed if status is "member" or any role (administrator/creator)
        if member.status in ("member", "administrator", "creator"):
            is_member = True
    except Exception:
        # An exception likely means the bot couldn't find the user (not a member or bot not an admin in channel)
        is_member = False

    if not is_member:
        # User is not subscribed to the channel – prompt to subscribe
        subscribe_btn = InlineKeyboardButton(text="Подписаться", url=f"https://t.me/{CHANNEL_USERNAME_GASTRO_PETER[1:]}")
        subscribe_kb = InlineKeyboardMarkup().add(subscribe_btn)
        # Format the prompt message with the channel username
        prompt_text = NOT_SUBSCRIBED_PROMPT.format(channel_name=CHANNEL_USERNAME_GASTRO_PETER)
        await call.message.answer(prompt_text, reply_markup=subscribe_kb)
    else:
        # User is subscribed – send the PDF file with a caption
        await bot.send_document(user_id, GASTRO_GUIDE_FILE_ID, caption=ALREADY_SUBSCRIBED_GASTRO)
    # Acknowledge the callback to remove "loading" state
    await call.answer()

@dp.callback_query_handler(lambda call: call.data == "guide_spb")
async def process_spb_guide(call: types.CallbackQuery):
    """Handles the inline button for 'Петербург до 1000 рублей'."""
    user_id = call.from_user.id
    # Check subscription status for the "Маленький Петербуржец" channel
    is_member = False
    try:
        member = await bot.get_chat_member(CHANNEL_ID_SMALL_PETER, user_id)
        if member.status in ("member", "administrator", "creator"):
            is_member = True
    except Exception:
        is_member = False

    if not is_member:
        # Not subscribed – prompt to subscribe to the channel
        subscribe_btn = InlineKeyboardButton(text="Подписаться", url=f"https://t.me/{CHANNEL_USERNAME_SMALL_PETER[1:]}")
        subscribe_kb = InlineKeyboardMarkup().add(subscribe_btn)
        prompt_text = NOT_SUBSCRIBED_PROMPT.format(channel_name=CHANNEL_USERNAME_SMALL_PETER)
        await call.message.answer(prompt_text, reply_markup=subscribe_kb)
    else:
        # Subscribed – send the PDF file with caption
        await bot.send_document(user_id, SMALL_PETER_FILE_ID, caption=ALREADY_SUBSCRIBED_SMALL)
    await call.answer()