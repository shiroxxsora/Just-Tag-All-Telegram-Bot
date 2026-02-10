"""Сервис тегов и случайного выбора: команды /all и /random."""

import random

from tagallbot.repository import ChatMemberRepository


class TagAllService:
    """Бизнес-логика команд /all и /random."""

    _RANDOM_OPTIONS = ("Идти на пару", "Не идти на пару")

    def __init__(self, chat_member_repository: ChatMemberRepository) -> None:
        self._repo = chat_member_repository

    async def get_admin_mentions(self, chat_id: int) -> str | None:
        """
        Возвращает строку с упоминаниями @username администраторов через пробел.
        None, если список пуст.
        """
        usernames = await self._repo.get_administrator_usernames(chat_id)
        if not usernames:
            return None
        return " ".join(f"@{u}" for u in usernames)

    def get_decision(self) -> str:
        """Возвращает случайное решение для команды /random."""
        return random.choice(self._RANDOM_OPTIONS)
