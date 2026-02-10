"""Контроллер LLM: команда /hello."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from tagallbot.service import LLMService


class LLMController:
    """Обработка команд, связанных с LLM."""

    def __init__(self, llm_service: LLMService) -> None:
        self._llm_service = llm_service

    @classmethod
    def create_router(cls, llm_service: LLMService) -> Router:
        router = Router()
        controller = cls(llm_service)
        router.message.register(controller.handle_hello, Command("hello"))
        return router

    async def handle_hello(self, message: Message) -> None:
        """Команда /hello — приветствие из LLM."""
        await message.answer(self._llm_service.get_greeting())
