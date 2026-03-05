"""Настройки приложения."""

from os import getenv


def _get_token() -> str:
    value = getenv("TOKEN")
    if not value:
        raise RuntimeError("Переменная окружения TOKEN не задана")
    return value


def _get_openrouter_key() -> str | None:
    return getenv("OPENROUTER_API_KEY")


TOKEN: str = _get_token()
OPENROUTER_API_KEY: str | None = _get_openrouter_key()
