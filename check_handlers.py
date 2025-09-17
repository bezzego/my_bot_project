# Небольшой скрипт для проверки, что обработчики зарегистрированы в общем Dispatcher
from config import dp
import handlers.start
import handlers.callbacks

if __name__ == '__main__':
    print('Message handlers зарегистрированы:', dp.message.handlers)
    print('Callback handlers зарегистрированы:', dp.callback_query.handlers)
