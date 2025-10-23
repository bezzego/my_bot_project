import asyncio
import logging

# Используем общий экземпляр bot и dp из config.py, где они созданы
from config import bot, dp

# Импортируем хэндлеры для регистрации событий (они регистрируются при импорте)
import handlers.start
import handlers.callbacks
import handlers.admin


async def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("Бот запускается…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
