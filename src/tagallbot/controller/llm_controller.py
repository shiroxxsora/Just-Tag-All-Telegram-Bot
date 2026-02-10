"""Контроллер LLM"""

import json
import logging
import random
import re
import httpx
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from tagallbot.service import LLMService

_log = logging.getLogger(__name__)
_USER_MESSAGE = "Сервис временно недоступен. Попробуйте позже."
_CONTEXT_MAX_TOKENS = 3000
_CHARS_PER_TOKEN = 4
_MIN_TRIGGER, _MAX_TRIGGER = 1, 1


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

        # Автор текущего сообщения
        if message.from_user:
            if message.from_user.username:
                author = f"@{message.from_user.username}"
            else:
                author = " ".join(
                    part
                    for part in (
                        message.from_user.first_name,
                        message.from_user.last_name,
                    )
                    if part
                ).strip() or "user"
        else:
            author = "user"

        # Добавляем в контекст с указанием автора
        state["messages"].append(f"{author}: {text}")
        self._trim_context_to_tokens(state["messages"])

        state["count"] += 1
        if state["count"] < state["next_trigger"]:
            return
        context = "\n".join(state["messages"])
        state["count"] = 0
        state["next_trigger"] = random.randint(_MIN_TRIGGER, _MAX_TRIGGER)

        _log.info("LLM context (chat_id=%s):\n%s", chat_id, context)

        # 1) Предварительный запрос: стоит ли вообще отвечать (ответ в JSON)
        decision_prompt = (
            "Ниже приведён недавний диалог в чате (формат 'Автор: текст'):\n"
            f"{context}\n\n"
            "Нужно ли боту TagAllBot ответить на последнее сообщение?\n"
            "Отвечай, если уместно поддержать разговор: приветствия, вопросы, реплики в тему, обращение к чату. "
            "Не отвечай на спам, голые ссылки, длинные копипасты, если тема явно не для бота.\n"
            "Ответь СТРОГО в формате JSON, без другого текста. Примеры:\n"
            '- ответить (приветствие, вопрос, реплика в тему): {"should_reply": true}\n'
            '- не отвечать (спам, офтоп, не к месту): {"should_reply": false}\n'
            "В ответе только один объект JSON с полем should_reply (boolean)."
        )
        try:
            decision_raw = await self._llm_service.ask(decision_prompt)
        except Exception as e:
            _log.exception("LLM decision error: %s", e)
            return

        if not decision_raw:
            return

        raw_from_api = decision_raw.strip()
        # Парсим JSON (модель может обернуть в ```json ... ``` или добавить текст)
        json_match = re.search(r'\{[^{}]*"should_reply"\s*:\s*(?:true|false)[^{}]*\}', raw_from_api)
        json_str = json_match.group(0) if json_match else raw_from_api
        try:
            data = json.loads(json_str)
            should_reply = bool(data.get("should_reply"))
        except (json.JSONDecodeError, TypeError) as e:
            _log.warning("LLM decision: invalid JSON (chat_id=%s), skip: %s", chat_id, e)
            return

        if not should_reply:
            _log.info("LLM decision: skip reply (chat_id=%s, raw=%r)", chat_id, raw_from_api)
            return

        # 2) Основной запрос — уже осмысленный ответ
        prompt = (
            "Ниже диалог в чате (формат 'Автор: текст'). Это только для контекста, повторять его нельзя.\n"
            f"{context}\n\n"
            f"Текущий автор последнего сообщения: {author}.\n"
            "Ты — бот, участник обсуждения. Напиши ТОЛЬКО свой короткий ответ (1–2 предложения).\n"
            "ЗАПРЕЩЕНО: копировать диалог выше, писать строки вида 'Автор: текст', цитировать чужие реплики. "
            "Только твой новый ответ, без префиксов и без повтора диалога."
        )
        try:
            reply = await self._llm_service.ask(prompt)
            if reply and reply not in ("Сервис временно недоступен.", "Внутренняя ошибка сервера."):
                await message.answer(reply)
                # Добавляем ответ бота в контекст
                state["messages"].append(f"You: {reply}")
                self._trim_context_to_tokens(state["messages"])
        except Exception as e:
            _log.exception("LLM context reply error: %s", e)
