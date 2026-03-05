"""Контроллер LLM: принимает запросы и передаёт их сервису."""

import logging
import httpx
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from tagallbot.service import LLMService

_log = logging.getLogger(__name__)
_USER_MESSAGE = "Сервис временно недоступен. Попробуйте позже."


def _author_from_message(message: Message) -> str:
    """Имя автора сообщения для контекста (username или имя)."""
    if not message.from_user:
        return "user"
    if message.from_user.username:
        return f"@{message.from_user.username}"
    parts = (message.from_user.first_name, message.from_user.last_name)
    name = " ".join(p for p in parts if p).strip()
    return name or "user"


class LLMController:
    """Принимает запросы и передаёт их в LLMService."""

    def __init__(self, llm_service: LLMService) -> None:
        self._llm_service = llm_service

    @classmethod
    def create_router(cls, llm_service: LLMService) -> Router:
        router = Router()
        controller = cls(llm_service)
        router.message.register(controller.handle_chat_message, F.text)
        return router

    async def handle_chat_message(self, message: Message) -> None:
        text = (message.text or "").strip()
        if not text or text.startswith("/") or (message.from_user and message.from_user.is_bot):
            return
        try:
            self._llm_service.enqueue_message(
                message.chat.id,
                text,
                _author_from_message(message),
            )
        except Exception as e:
            _log.exception("LLM chat error: %s", e)
