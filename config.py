"""
Configuration — reads from environment variables / .env file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ── Telegram ──────────────────────────────────────────────────────────────
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # Comma-separated list of numeric Telegram user IDs allowed to use the bot.
    # Leave empty to allow everyone (not recommended for private bots).
    _raw_ids: str = os.getenv("ALLOWED_USER_IDS", "")
    ALLOWED_USER_IDS: List[int] = (
        [int(i.strip()) for i in _raw_ids.split(",") if i.strip()]
        if _raw_ids.strip()
        else []
    )

    # ── Session ───────────────────────────────────────────────────────────────
    # How long (seconds) an idle session lives before auto-expiry
    SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "3600"))
    # Maximum files a single user can queue at once
    MAX_FILES_PER_USER: int = int(os.getenv("MAX_FILES_PER_USER", "200"))

    # ── Storage ───────────────────────────────────────────────────────────────
    # Base temp directory for downloads; defaults to <project>/tmp/
    TEMP_DIR: Path = Path(os.getenv("TEMP_DIR", Path(__file__).parent / "tmp"))

    # ── ZIP ───────────────────────────────────────────────────────────────────
    # Telegram upload limit in bytes (default 2 GB)
    TG_FILE_SIZE_LIMIT: int = int(
        os.getenv("TG_FILE_SIZE_LIMIT", str(2 * 1024 ** 3))
    )
    # Folder name prefix inside the ZIP archive
    ZIP_FOLDER_PREFIX: str = os.getenv("ZIP_FOLDER_PREFIX", "Playlist")

    # ── Rate limiting ─────────────────────────────────────────────────────────
    # Max /zip commands per user per minute
    ZIP_RATE_LIMIT: int = int(os.getenv("ZIP_RATE_LIMIT", "3"))

    # ── Download ──────────────────────────────────────────────────────────────
    # Number of retry attempts on download failure
    DOWNLOAD_RETRIES: int = int(os.getenv("DOWNLOAD_RETRIES", "3"))

    def validate(self) -> None:
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is not set. Check your .env file.")
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.validate()
