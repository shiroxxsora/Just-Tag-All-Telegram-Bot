from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

TOKEN = getenv('TOKEN')

dp = Dispatcher()


@dp.message(Command('all'))
async def command_all_handler(message: Message) -> None:
    """
    This handler receives messages with `/all` command
    """
    try:
        bot = message.bot
        members = await bot.get_chat_administrators(message.chat.id)

        message_text = ''
        for member in members:
            if member.user.username:
                message_text += f'@{member.user.username} '

        if message_text:
            await message.answer(message_text)
        else:
            await message.answer("Не удалось получить список участников")

    except Exception as e:
        await message.answer(f"Ошибка: {str(e)}")


async def start() -> None:
    print("Starting Tag all telegram bot...")
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    await dp.start_polling(bot)
