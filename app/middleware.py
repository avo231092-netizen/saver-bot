from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from typing import Any, Awaitable, Callable, Dict
from app import db


class SubscriptionMiddleware(BaseMiddleware):
    """Check user subscription tier on every update."""
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")
        if user:
            await db.get_user(user.id, user.username, user.first_name)
            has_access, tier, limit_sub, limit_track, msg = await db.check_access(user.id)
            data["tier"] = tier
            data["limit_sub"] = limit_sub
            data["limit_track"] = limit_track
            data["access_msg"] = msg
        return await handler(event, data)
