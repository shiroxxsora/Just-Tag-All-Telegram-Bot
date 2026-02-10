"""Контроллеры и единая точка регистрации роутеров."""

from aiogram import Bot, Router

from tagallbot.repository import ChatMemberRepository
from tagallbot.service import LLMService, TagAllService

from .llm_controller import LLMController
from .tags_controller import TagsController


def get_routers(bot: Bot) -> list[Router]:
    chat_member_repository = ChatMemberRepository(bot)
    tag_all_service = TagAllService(chat_member_repository)
    llm_service = LLMService()

    return [
        TagsController.create_router(tag_all_service),
        LLMController.create_router(llm_service),
    ]


__all__ = ["TagsController", "LLMController", "get_routers"]
