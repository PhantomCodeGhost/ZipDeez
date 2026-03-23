"""
Telegram Media Packager Bot — Entry Point
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from bot.handlers.commands import router as commands_router
from bot.handlers.media import router as media_router
from bot.middlewares.auth import AuthMiddleware
from services.session import SessionManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Starting Media Packager Bot...")

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    session_manager = SessionManager(
        session_ttl=settings.SESSION_TTL_SECONDS,
        max_files_per_user=settings.MAX_FILES_PER_USER,
    )

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Inject dependencies into routers via workflow data
    dp["session_manager"] = session_manager

    # Register middlewares
    dp.message.middleware(AuthMiddleware(allowed_ids=settings.ALLOWED_USER_IDS))

    # Register routers
    dp.include_router(commands_router)
    dp.include_router(media_router)

    # Start background cleanup task
    asyncio.create_task(session_manager.auto_cleanup_loop())

    logger.info("Bot is ready. Polling...")
    try:
        await dp.start_polling(bot, allowed_updates=["message"])
    finally:
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
