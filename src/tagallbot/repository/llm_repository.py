"""Репозиторий вызовов LLM через OpenRouter API."""

import logging
import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/auto"
_log = logging.getLogger(__name__)


class LLMRepository:
    """Обращения к модели: только HTTP-запрос к OpenRouter, без бизнес-логики."""

    def __init__(self, api_key: str | None) -> None:
        self._api_key = api_key

    async def ask(
        self,
        user_message: str,
        *,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 256,
    ) -> str:
        """Отправить сообщение в LLM и вернуть текст ответа. Бросает httpx.HTTPStatusError при ошибке API."""
        _log.debug("LLM model: %s", model)
        if not self._api_key:
            _log.error("OPENROUTER_API_KEY не задан. Укажите ключ в переменных окружения.")
            raise ValueError("OPENROUTER_API_KEY не задан.")
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": user_message}],
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(OPENROUTER_URL, json=payload, headers=headers)
            resp.raise_for_status()
        data = resp.json()
        choice = data.get("choices") and data["choices"][0]
        if not choice:
            return "Пустой ответ от модели."
        message = choice.get("message") or {}
        return (message.get("content") or "").strip() or "Пустой ответ."
