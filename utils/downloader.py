"""
Async file downloader — streams Telegram files to disk with retry logic.

Files are downloaded via the Telegram Bot API (getFile + download_file).
No re-encoding or metadata modification occurs; bytes are written verbatim.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

from aiogram import Bot

logger = logging.getLogger(__name__)

# Characters not safe for filenames on Windows / Linux
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize(name: str, max_len: int = 200) -> str:
    """Replace unsafe characters and truncate."""
    safe = _UNSAFE.sub("_", name).strip(". ")
    return safe[:max_len] if safe else "file"


class FileDownloader:
    def __init__(self, bot: Bot, temp_dir: Path) -> None:
        self.bot = bot
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def download(
        self,
        file_id: str,
        filename: str,
        retries: int = 3,
    ) -> Path:
        """
        Download a Telegram file by file_id to *temp_dir*.

        Returns the local Path on success.
        Raises the last exception if all retries fail.
        """
        safe_name = _sanitize(filename)
        dest = self._unique_path(safe_name)

        last_exc: Optional[Exception] = None
        for attempt in range(1, retries + 1):
            try:
                tg_file = await self.bot.get_file(file_id)
                await self.bot.download_file(tg_file.file_path, destination=dest)
                logger.info(
                    "Downloaded '%s' → %s (%.1f KB)",
                    filename,
                    dest.name,
                    dest.stat().st_size / 1024,
                )
                return dest
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Download attempt %d/%d failed for '%s': %s",
                    attempt,
                    retries,
                    filename,
                    exc,
                )
                if attempt < retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential back-off

        # Clean up partial file if it exists
        dest.unlink(missing_ok=True)
        raise last_exc  # type: ignore[misc]

    def cleanup(self, files: List[Tuple[Path, str]]) -> None:
        """Delete locally downloaded files."""
        for local_path, _ in files:
            try:
                local_path.unlink(missing_ok=True)
                logger.debug("Deleted temp file: %s", local_path)
            except Exception as exc:
                logger.warning("Could not delete %s: %s", local_path, exc)

    # ── helpers ────────────────────────────────────────────────────────────────

    def _unique_path(self, name: str) -> Path:
        """Return a path that does not already exist (appends counter if needed)."""
        candidate = self.temp_dir / name
        if not candidate.exists():
            return candidate

        stem, _, ext = name.rpartition(".")
        if not stem:
            stem, ext = name, ""
        else:
            ext = "." + ext

        counter = 2
        while True:
            candidate = self.temp_dir / f"{stem} ({counter}){ext}"
            if not candidate.exists():
                return candidate
            counter += 1
