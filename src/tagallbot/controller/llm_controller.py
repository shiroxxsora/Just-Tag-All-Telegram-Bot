"""Контроллер LLM"""

import logging
import random
import httpx
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from tagallbot.service import LLMService

_log = logging.getLogger(__name__)
_USER_MESSAGE = "Сервис временно недоступен. Попробуйте позже."
_CONTEXT_MAX_TOKENS = 500
_CHARS_PER_TOKEN = 4
_MIN_TRIGGER, _MAX_TRIGGER = 1, 2


def _approx_tokens(text: str) -> int:
    """Приблизительное число токенов по длине текста."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


class LLMController:
    """Обработка команд, связанных с LLM."""

    def __init__(self, llm_service: LLMService) -> None:
        self._llm_service = llm_service
        # chat_id -> {"count": int, "messages": list[str], "next_trigger": int}
        # todo переделать под бд
        self._chat_state: dict[int, dict] = {}

    @classmethod
    def create_router(cls, llm_service: LLMService) -> Router:
        router = Router()
        controller = cls(llm_service)
        router.message.register(controller.handle_hello, Command("hello"))
        router.message.register(controller.handle_chat_message, F.text)
        return router

    def _get_state(self, chat_id: int) -> dict:
        if chat_id not in self._chat_state:
            self._chat_state[chat_id] = {
                "count": 0,
                "messages": [],
                "next_trigger": random.randint(_MIN_TRIGGER, _MAX_TRIGGER),
            }
        return self._chat_state[chat_id]

    async def handle_hello(self, message: Message) -> None:
        """Команда /hello — приветствие из LLM."""
        try:
            text = await self._llm_service.get_greeting()
            await message.answer(text)
        except httpx.HTTPStatusError as e:
            _log.exception("OpenRouter API error: %s", e.response.status_code)
            await message.answer(_USER_MESSAGE)
        except Exception as e:
            _log.exception("LLM error: %s", e)
            await message.answer(_USER_MESSAGE)

    def _trim_context_to_tokens(self, messages: list[str], max_tokens: int = _CONTEXT_MAX_TOKENS) -> None:
        """Оставляет в messages только последние сообщения, укладывающиеся в max_tokens."""
        total = sum(_approx_tokens(m) for m in messages)
        while messages and total > max_tokens:
            total -= _approx_tokens(messages.pop(0))

    async def handle_chat_message(self, message: Message) -> None:
        """На каждое 5–10 сообщение отвечает LLM с учётом контекста (~500 токенов)."""
        text = (message.text or "").strip()
        if not text or text.startswith("/") or (message.from_user and message.from_user.is_bot):
            return
        chat_id = message.chat.id
        state = self._get_state(chat_id)
        state["messages"].append(text)
        self._trim_context_to_tokens(state["messages"])
        state["count"] += 1
        if state["count"] < state["next_trigger"]:
            return
        context = "\n".join(state["messages"])
        state["count"] = 0
        state["next_trigger"] = random.randint(_MIN_TRIGGER, _MAX_TRIGGER)
        _log.info("LLM context (chat_id=%s):\n%s", chat_id, context)
        prompt = (
            "Последние сообщения в чате:\n"
            f"{context}\n\n"
            "Ответь кратко и по делу, как участник обсуждения."
        )
        try:
            reply = await self._llm_service.ask(prompt)
            if reply and reply not in ("Сервис временно недоступен.", "Внутренняя ошибка сервера."):
                await message.answer(reply)
        except Exception as e:
            _log.exception("LLM context reply error: %s", e)
