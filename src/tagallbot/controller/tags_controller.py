"""Контроллер тегов: команды /all, /random."""

import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from tagallbot.service import TagAllService

_log = logging.getLogger(__name__)


class TagsController:
    """Обработка команд, связанных с тегами и простой логикой (/all, /random)."""

    def __init__(self, tag_all_service: TagAllService) -> None:
        self._tag_all_service = tag_all_service

    @classmethod
    def create_router(cls, tag_all_service: TagAllService) -> Router:
        router = Router()
        controller = cls(tag_all_service)
        router.message.register(controller.handle_all, Command("all"))
        router.message.register(controller.handle_random, Command("random"))
        return router

    async def handle_all(self, message: Message) -> None:
        """Команда /all — ответ списком @username администраторов."""
        try:
            text = await self._tag_all_service.get_admin_mentions(message.chat.id)
            await message.answer(text or "Не удалось получить список участников")
        except Exception as e:
            _log.exception("TagAll error: %s", e)
            await message.answer("Произошла ошибка. Попробуйте позже.")

    async def handle_random(self, message: Message) -> None:
        """Команда /random — случайное решение."""
        decision = self._tag_all_service.get_decision()
        await message.answer(f"🎲 Решение: {decision}")
