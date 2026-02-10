"""Контроллеры и единая точка регистрации роутеров."""

from functools import partial
from aiogram import Bot, Router

from tagallbot.config import OPENROUTER_API_KEY
from tagallbot.repository import ChatMemberRepository, LLMRepository
from tagallbot.service import LLMService, TagAllService

from .llm_controller import LLMController
from .tags_controller import TagsController


async def _send_reply(chat_id: int, reply: str, *, bot: Bot) -> None:
    await bot.send_message(chat_id, reply)


def get_routers(bot: Bot) -> list[Router]:
    chat_member_repository = ChatMemberRepository(bot)
    tag_all_service = TagAllService(chat_member_repository)
    llm_repository = LLMRepository(api_key=OPENROUTER_API_KEY)
    on_reply = partial(_send_reply, bot=bot)
    llm_service = LLMService(llm_repository, on_reply=on_reply)

    return [
        TagsController.create_router(tag_all_service),
        LLMController.create_router(llm_service),
    ]


__all__ = ["TagsController", "LLMController", "get_routers"]
