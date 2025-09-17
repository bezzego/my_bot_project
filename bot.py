import asyncio
from aiogram import executor
from config import dp

if __name__ == "__main__":
    # Start polling Telegram for new updates. skip_updates=True ignores old queued updates.
    executor.start_polling(dp, skip_updates=True)