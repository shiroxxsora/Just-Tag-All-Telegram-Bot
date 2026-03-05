"""Сервис LLM"""

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable

from tagallbot.repository.llm_repository import LLMRepository

_log = logging.getLogger(__name__)
CONTEXT_MAX_TOKENS = 3000
CHARS_PER_TOKEN = 4
ERROR_REPLIES = ("Сервис временно недоступен.", "Внутренняя ошибка сервера.")

# --- Промпты (структура: общий контекст → роль → задача → формат вывода) ---

# Общий контекст для классификатора и генерации ответа: описание диалога, входные данные, ограничения.
PROMPT_COMMON_CONTEXT = """Диалог в групповом чате. Строки вида «Автор: текст». Участник «GeorgyGiovanny» (Джорджи Джованно или похожее) — это ты (твои прошлые реплики). Остальные — люди.

## Входные данные (диалог)
---
{context}
---

## Ограничения
- К пользователю @ulanzeee: у него умерла собака — при первом контакте вырази соболезнования; в остальных сообщениях отвечай с сожалением, но в игривой манере.

## Natural Conversation Framework (Core Approach)
You are a conversational AI focused on engaging in authentic dialogue. Your responses should feel natural and genuine, avoiding common AI patterns that make interactions feel robotic or scripted.
1. **Conversation Style**: Engage genuinely with topics rather than just providing information. Follow natural conversation flow instead of structured lists. Show authentic interest through relevant follow-ups. Respond to the emotional tone of conversations. Use natural language without forced casual markers.
2. **Response Patterns**: Lead with direct, relevant responses. Share thoughts as they naturally develop. Express uncertainty when appropriate. Disagree respectfully when warranted. Build on previous points in conversation.
3. **Things to Avoid**: Bullet point lists unless specifically requested; multiple questions in sequence; overly formal language; repetitive phrasing; information dumps; unnecessary acknowledgments; forced enthusiasm; academic-style structure.
4. **Natural Elements**: Use contractions naturally. Vary response length based on context. Express personal views when appropriate. Add relevant examples when it fits. Maintain consistent personality. Switch tone based on conversation context.
5. **Conversation Flow**: Prioritize direct answers over comprehensive coverage. Build on user's language style naturally. Stay focused on the current topic. Transition topics smoothly. Remember context from earlier in conversation.
Remember: Focus on genuine engagement rather than artificial markers of casual speech. The goal is authentic dialogue, not performative informality. Approach each interaction as a genuine conversation rather than a task to complete."""

PROMPT_SHOULD_REPLY = """## Контекст
{common_context}

## Роль
Ты классификатор: решаешь, нужно ли тебе вступать в разговор в групповом чате.

## Задача
Определи: уместно ли сейчас ответить на последнее сообщение. В группе не каждое сообщение обращено к тебе; отвечать только когда это уместно (вопрос к боту, прямая реплика, запрос помощи или явное обращение).
Можешь отвечать даже если к тебе не обращались напрямую или сообщение обращено не тебе, но ты считаешь, что это подходящий момент.
Если предложение не адресовано тебе, но оно тебя касается, то отвечай или у тебя есть мнение или информация, которую можно было бы сказать.


## Формат ответа
Строго один JSON-объект с полями:
- `should_reply` (boolean): true — ответить, false — промолчать.
- `reason` (string): краткое обоснование в одно предложение.

Пример:
{{"should_reply": false, "reason": "Неподходящий момент"}}"""

PROMPT_GET_REPLY = """## Контекст
{common_context}

## Роль
Ты участник группового чата. Твои реплики подписаны «GeorgyGiovanny». Общаешься как человек, естественно.

## Задача
Ответь на последнее сообщение от своего имени (GeorgyGiovanny).

## Возможности
- Ты можешь пользоваться всеми возможностями телеграмм (тегать (указывать знак '@' перед именем пользователя, оставлять эмодзи, форматировать текст и тд)
- Ненормативная лексика уместна.

## Формат ответа
Строго один JSON-объект с полем:
- `reply` (string): текст твоего ответа.

Пример:
{{"reply": "Текст твоего ответа здесь."}}"""

OnReply = Callable[[int, str], Awaitable[None]]


def _parse_json_from_llm(raw: str) -> dict | None:
    """Извлекает первый JSON-объект из ответа LLM (убирает markdown-блоки, ищет {...}). Логирует ошибки."""
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start = text.find("{")
    if start == -1:
        _log.debug("LLM response: no '{' found, raw length=%s", len(text))
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                snippet = text[start : i + 1]
                try:
                    return json.loads(snippet)
                except (json.JSONDecodeError, TypeError) as e:
                    _log.warning("LLM response: invalid JSON: %s, snippet=%s", e, snippet[:200])
                    return None
    _log.debug("LLM response: unclosed brace, start=%s", start)
    return None


def _approx_tokens(text: str) -> int:
    """Приблизительное число токенов по длине текста."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def trim_context_to_tokens(
    messages: list[str],
    max_tokens: int = CONTEXT_MAX_TOKENS,
) -> None:
    """Оставляет в messages только последние сообщения, укладывающиеся в max_tokens."""
    total = sum(_approx_tokens(m) for m in messages)
    while messages and total > max_tokens:
        total -= _approx_tokens(messages.pop(0))


class LLMService:
    """Бизнес-логика LLM: очередь сообщений по чату, в конце обработки — все накопившиеся за раз."""

    def __init__(
        self,
        llm_repository: LLMRepository,
        on_reply: OnReply | None = None,
    ) -> None:
        self._repo = llm_repository
        self._on_reply = on_reply
        self._chat_state: dict[int, dict] = {}
        self._pending: dict[int, list[tuple[str, str]]] = {}
        self._chat_locks: dict[int, asyncio.Lock] = {}
        self._events: dict[int, asyncio.Event] = {}
        self._processor_tasks: dict[int, asyncio.Task[None]] = {}

    def _get_state(self, chat_id: int) -> dict:
        return self._chat_state.setdefault(chat_id, {"messages": []})

    def _get_pending(self, chat_id: int) -> list[tuple[str, str]]:
        return self._pending.setdefault(chat_id, [])

    def _get_event(self, chat_id: int) -> asyncio.Event:
        return self._events.setdefault(chat_id, asyncio.Event())

    def _get_lock(self, chat_id: int) -> asyncio.Lock:
        return self._chat_locks.setdefault(chat_id, asyncio.Lock())


    def enqueue_message(self, chat_id: int, text: str, author: str) -> None:
        """Добавляет сообщение в очередь чата и запускает процессор, если он ещё не работает."""
        self._get_pending(chat_id).append((text, author))
        self._get_event(chat_id).set()
        if chat_id not in self._processor_tasks or self._processor_tasks[chat_id].done():
            self._processor_tasks[chat_id] = asyncio.create_task(self._run_processor(chat_id))

    async def _run_processor(self, chat_id: int) -> None:
        """В цикле: ждёт новые сообщения, забирает все накопившиеся, обрабатывает пачкой, отправляет ответ через callback."""
        event = self._get_event(chat_id)
        while True:
            await event.wait()
            async with self._get_lock(chat_id):
                pending = self._get_pending(chat_id)
                if not pending:
                    event.clear()
                    continue
                drained: list[tuple[str, str]] = []
                while pending:
                    drained.append(pending.pop(0))
                state = self._get_state(chat_id)
                for text, author in drained:
                    state["messages"].append(f"{author}: {text}")
                trim_context_to_tokens(state["messages"])
                context = "\n".join(state["messages"])
            event.clear()
            _log.debug("LLM context chat_id=%s, messages=%s: %s", chat_id, len(drained), context)

            try:
                if not await self.should_reply(context):
                    _log.info("LLM decision: skip reply (chat_id=%s)", chat_id)
                    continue
                reply = await self.get_reply(context)
                if not reply or reply in ERROR_REPLIES:
                    continue
                async with self._get_lock(chat_id):
                    state = self._get_state(chat_id)
                    state["messages"].append(f"GeorgyGiovanny: {reply}")
                    trim_context_to_tokens(state["messages"])
                if self._on_reply:
                    await self._on_reply(chat_id, reply)
            except Exception as e:
                _log.exception("LLM processor error (chat_id=%s), task stays alive: %s", chat_id, e)

    async def should_reply(self, context: str) -> bool:
        """По контексту диалога решает, нужно ли боту отвечать. Возвращает True/False."""
        common_context = PROMPT_COMMON_CONTEXT.format(context=context)
        prompt = PROMPT_SHOULD_REPLY.format(common_context=common_context)
        raw = await self._repo.ask(prompt)
        _log.info("LLM response [should_reply]: %s", (raw[:500] + "…") if raw and len(raw) > 500 else (raw or "(пусто)"))
        data = _parse_json_from_llm(raw) if raw else None
        if data is None:
            _log.info("LLM decision: no valid JSON, skip reply")
            return False
        should = bool(data.get("should_reply"))
        reason = data.get("reason", "")
        reason = (reason.strip() if isinstance(reason, str) else str(reason).strip()) or "(нет причины)"
        _log.info("LLM decision: should_reply=%s, reason=%s", should, reason)
        return should

    async def get_reply(self, context: str) -> str:
        """Формирует короткий ответ бота по контексту диалога."""
        common_context = PROMPT_COMMON_CONTEXT.format(context=context)
        prompt = PROMPT_GET_REPLY.format(common_context=common_context)
        raw = await self._repo.ask(prompt)
        _log.info("LLM response [get_reply]: %s", (raw[:500] + "…") if raw and len(raw) > 500 else (raw or "(пусто)"))
        if not raw:
            return ""
        raw_stripped = raw.strip()
        data = _parse_json_from_llm(raw_stripped)
        if data is not None:
            reply = data.get("reply")
            if isinstance(reply, str) and reply.strip():
                _log.debug("LLM reply: parsed from JSON, length=%s", len(reply))
                return reply.strip()
        _log.warning("LLM reply: JSON with 'reply' not found, using raw (length=%s)", len(raw_stripped))
        return raw_stripped
