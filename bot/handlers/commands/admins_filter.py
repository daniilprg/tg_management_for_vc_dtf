from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from bot.config import ADMINS

class AdminFilter(BaseFilter):
    async def __call__(self, obj: Message | CallbackQuery) -> bool:
        return obj.from_user.id in ADMINS