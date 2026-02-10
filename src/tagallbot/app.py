"""Точка входа: сборка слоёв и запуск бота."""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from tagallbot.config import TOKEN
from tagallbot.controller import get_routers


async def start() -> None:
    print("Starting Tag all telegram bot...")
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    for router in get_routers(bot):
        dp.include_router(router)

    await dp.start_polling(bot)
