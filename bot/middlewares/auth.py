"""
Authentication middleware — restricts bot to whitelisted Telegram user IDs.
If ALLOWED_USER_IDS is empty, all users are permitted.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, List

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    def __init__(self, allowed_ids: List[int]) -> None:
        self.allowed_ids = set(allowed_ids)
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        user = event.from_user
        if not user:
            return  # Ignore anonymous messages

        if self.allowed_ids and user.id not in self.allowed_ids:
            logger.warning(
                "Unauthorized access attempt from user_id=%s username=%s",
                user.id,
                user.username,
            )
            await event.answer(
                "⛔ <b>Access Denied.</b>\n"
                "This is a private bot. You are not authorized to use it.",
            )
            return

        return await handler(event, data)
