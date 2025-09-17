import asyncio
import traceback

from config import bot, CHANNEL_ID_GASTRO_PETER, CHANNEL_ID_SMALL_PETER, CHANNEL_USERNAME_GASTRO_PETER, CHANNEL_USERNAME_SMALL_PETER

async def check():
    print('CHANNEL_ID_GASTRO_PETER =', CHANNEL_ID_GASTRO_PETER)
    print('CHANNEL_ID_SMALL_PETER  =', CHANNEL_ID_SMALL_PETER)
    print('CHANNEL_USERNAME_GASTRO_PETER =', CHANNEL_USERNAME_GASTRO_PETER)
    print('CHANNEL_USERNAME_SMALL_PETER  =', CHANNEL_USERNAME_SMALL_PETER)

    for name, ident in [
        ('gastro id', CHANNEL_ID_GASTRO_PETER),
        ('spb id', CHANNEL_ID_SMALL_PETER),
        ('gastro username', CHANNEL_USERNAME_GASTRO_PETER),
        ('spb username', CHANNEL_USERNAME_SMALL_PETER),
    ]:
        try:
            print(f'\nTrying get_chat for {name} ({ident})')
            chat = await bot.get_chat(ident)
            print('get_chat OK:', chat)
        except Exception as e:
            print('get_chat ERROR for', name, type(e), e)
            traceback.print_exc()

    # Try get_chat_member for ids (safe: may raise if chat not found or bot not admin)
    try:
        print('\nTrying get_chat_member for CHANNEL_ID_GASTRO_PETER with bot as chat')
        # Note: use an example user id 1 to check response; in real test use your user id
        member = await bot.get_chat_member(CHANNEL_ID_GASTRO_PETER, 1)
        print('get_chat_member OK:', member)
    except Exception as e:
        print('get_chat_member ERROR:', type(e), e)
        traceback.print_exc()

async def main():
    await check()
    await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
