"""
Command handlers: /start  /status  /clear  /zip
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from pathlib import Path

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from config import settings
from services.session import SessionManager
from services.zipper import ZipService
from utils.downloader import FileDownloader

router = Router()
logger = logging.getLogger(__name__)

# Simple in-memory rate limiter: user_id → list of timestamps
_zip_calls: dict[int, list[float]] = defaultdict(list)


def _check_rate_limit(user_id: int) -> bool:
    """Returns True if user is within rate limit, False if exceeded."""
    now = time.monotonic()
    window = 60.0  # 1 minute window
    calls = [t for t in _zip_calls[user_id] if now - t < window]
    _zip_calls[user_id] = calls
    if len(calls) >= settings.ZIP_RATE_LIMIT:
        return False
    _zip_calls[user_id].append(now)
    return True


# ── /start ────────────────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message, session_manager: SessionManager) -> None:
    user_id = message.from_user.id
    session_manager.get_or_create(user_id)
    await message.answer(
        "🎵 <b>Media Packager Bot</b>\n\n"
        "Forward audio files or documents to me and I'll bundle them into a "
        "single ZIP archive — preserving the original files byte-for-byte.\n\n"
        "<b>Commands:</b>\n"
        "  /status  — see how many files are queued\n"
        "  /zip     — download & create ZIP archive\n"
        "  /clear   — reset your queue\n\n"
        "Start forwarding files! 📂"
    )


# ── /status ───────────────────────────────────────────────────────────────────

@router.message(Command("status"))
async def cmd_status(message: Message, session_manager: SessionManager) -> None:
    user_id = message.from_user.id
    session = session_manager.get_or_create(user_id)
    count = len(session.files)
    if count == 0:
        await message.answer("📭 Your queue is empty. Forward some files first!")
    else:
        lines = [f"📦 <b>{count} file(s) queued:</b>\n"]
        for i, f in enumerate(session.files, 1):
            lines.append(f"  {i}. {f.display_name}")
        await message.answer("\n".join(lines))


# ── /clear ────────────────────────────────────────────────────────────────────

@router.message(Command("clear"))
async def cmd_clear(message: Message, session_manager: SessionManager) -> None:
    user_id = message.from_user.id
    session_manager.clear(user_id)
    await message.answer("🗑️ Queue cleared. Ready for new files!")


# ── /zip ──────────────────────────────────────────────────────────────────────

@router.message(Command("zip"))
async def cmd_zip(
    message: Message,
    session_manager: SessionManager,
    bot: Bot,
) -> None:
    user_id = message.from_user.id

    # Rate limit check
    if not _check_rate_limit(user_id):
        await message.answer(
            f"⚠️ Slow down! You can run /zip at most {settings.ZIP_RATE_LIMIT} "
            "times per minute."
        )
        return

    session = session_manager.get_or_create(user_id)

    if not session.files:
        await message.answer("📭 Nothing to zip yet. Forward some files first!")
        return

    total = len(session.files)
    status_msg = await message.answer(
        f"⏳ Starting download of <b>{total}</b> file(s)…"
    )

    downloader = FileDownloader(bot=bot, temp_dir=settings.TEMP_DIR)
    zip_service = ZipService(temp_dir=settings.TEMP_DIR)

    downloaded: list[tuple[Path, str]] = []   # (local_path, archive_name)
    failed: list[str] = []

    # ── Download phase ────────────────────────────────────────────────────────
    for idx, file_entry in enumerate(session.files, 1):
        try:
            await status_msg.edit_text(
                f"⬇️ Downloading <b>{idx}/{total}</b>: {file_entry.display_name}…"
            )
            local_path = await downloader.download(
                file_id=file_entry.file_id,
                filename=file_entry.display_name,
                retries=settings.DOWNLOAD_RETRIES,
            )
            downloaded.append((local_path, file_entry.display_name))
        except Exception as exc:
            logger.error(
                "Failed to download %s for user %s: %s",
                file_entry.display_name,
                user_id,
                exc,
            )
            failed.append(file_entry.display_name)

    if not downloaded:
        await status_msg.edit_text(
            "❌ All downloads failed. Please try again later."
        )
        return

    # ── ZIP creation phase ────────────────────────────────────────────────────
    await status_msg.edit_text("🗜️ Creating ZIP archive…")

    try:
        zip_parts = zip_service.create_zip(
            files=downloaded,
            prefix=settings.ZIP_FOLDER_PREFIX,
            size_limit=settings.TG_FILE_SIZE_LIMIT,
        )
    except Exception as exc:
        logger.error("ZIP creation failed for user %s: %s", user_id, exc)
        await status_msg.edit_text("❌ Failed to create ZIP. Please try again.")
        downloader.cleanup(downloaded)
        return

    # ── Send phase ────────────────────────────────────────────────────────────
    part_count = len(zip_parts)
    for part_idx, zip_path in enumerate(zip_parts, 1):
        label = f" (Part {part_idx}/{part_count})" if part_count > 1 else ""
        await status_msg.edit_text(
            f"📤 Sending ZIP{label}… ({_fmt_size(zip_path.stat().st_size)})"
        )
        try:
            await bot.send_document(
                chat_id=message.chat.id,
                document=FSInputFile(zip_path, filename=zip_path.name),
                caption=(
                    f"✅ <b>{len(downloaded)} file(s)</b> packed{label}\n"
                    + (
                        f"⚠️ <b>{len(failed)} file(s) skipped</b> (download error)"
                        if failed
                        else ""
                    )
                ),
            )
        except Exception as exc:
            logger.error("Failed to send ZIP part %s: %s", zip_path.name, exc)
            await message.answer(
                f"❌ Could not send <code>{zip_path.name}</code>. "
                "The file may be too large for Telegram."
            )

    # ── Cleanup ───────────────────────────────────────────────────────────────
    await status_msg.delete()
    downloader.cleanup(downloaded)
    zip_service.cleanup(zip_parts)
    session_manager.clear(user_id)

    if failed:
        skipped = "\n".join(f"  • {n}" for n in failed)
        await message.answer(
            f"⚠️ <b>Skipped {len(failed)} file(s)</b> due to download errors:\n"
            + skipped
        )


# ── helpers ───────────────────────────────────────────────────────────────────

def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"
