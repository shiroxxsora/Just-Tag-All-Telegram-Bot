"""Сервис LLM через OpenRouter API."""

import logging
import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-3.5-turbo"
_log = logging.getLogger(__name__)


class LLMService:
    """Минимальный клиент OpenRouter: один запрос — один ответ."""

    def __init__(self, api_key: str | None) -> None:
        self._api_key = api_key

    async def ask(self, user_message: str, *, model: str = DEFAULT_MODEL) -> str:
        """Отправить сообщение в LLM и вернуть текст ответа."""
        if not self._api_key:
            _log.error("OPENROUTER_API_KEY не задан. Укажите ключ в переменных окружения.")
            return "Внутренняя ошибка сервера."
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": user_message}],
            "max_tokens": 256,
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

    async def get_greeting(self) -> str:
        """Приветствие от LLM (одна короткая фраза)."""
        return await self.ask("Напиши одно короткое приветствие на русском, без лишнего.")
