"""Репозиторий участников чата."""

from aiogram import Bot


class ChatMemberRepository:
    """Доступ к данным участников чата через Telegram API."""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def get_administrator_usernames(self, chat_id: int) -> list[str]:
        """Возвращает список username администраторов чата (без @)."""
        members = await self._bot.get_chat_administrators(chat_id)
        result: list[str] = []
        for member in members:
            if member.user.username:
                result.append(member.user.username)
        return result
