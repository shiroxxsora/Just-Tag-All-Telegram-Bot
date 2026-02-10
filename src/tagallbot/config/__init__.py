"""Настройки приложения."""

from os import getenv


def _get_token() -> str:
    value = getenv("TOKEN")
    if not value:
        raise RuntimeError("Переменная окружения TOKEN не задана")
    return value


TOKEN: str = _get_token()
