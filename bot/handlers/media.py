"""
Media handler — receives forwarded Audio and Document messages.
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import Message

from config import settings
from services.session import FileEntry, SessionManager

router = Router()
logger = logging.getLogger(__name__)


def _extract_entry(message: Message) -> FileEntry | None:
    """
    Pull file_id, file_unique_id, and a display name from an Audio or Document
    message. Returns None if the message contains neither.
    """
    if message.audio:
        media = message.audio
        # Prefer performer + title, fall back to file name, then a generic label
        name = (
            media.file_name
            or _build_audio_name(media.performer, media.title)
            or "audio_file"
        )
        return FileEntry(
            file_id=media.file_id,
            file_unique_id=media.file_unique_id,
            display_name=_ensure_extension(name, ".mp3"),
            mime_type=media.mime_type or "audio/mpeg",
            file_size=media.file_size or 0,
        )

    if message.document:
        media = message.document
        name = media.file_name or "document"
        return FileEntry(
            file_id=media.file_id,
            file_unique_id=media.file_unique_id,
            display_name=name,
            mime_type=media.mime_type or "application/octet-stream",
            file_size=media.file_size or 0,
        )

    return None


def _build_audio_name(performer: str | None, title: str | None) -> str | None:
    parts = [p for p in (performer, title) if p]
    return " - ".join(parts) if parts else None


def _ensure_extension(name: str, ext: str) -> str:
    """Add extension if the name has none."""
    if "." in name.rsplit("/", 1)[-1]:
        return name
    return name + ext


# ── handler ───────────────────────────────────────────────────────────────────

@router.message()
async def handle_media(message: Message, session_manager: SessionManager) -> None:
    entry = _extract_entry(message)

    if entry is None:
        # Not a file — ignore silently (commands are handled by their own router)
        return

    user_id = message.from_user.id
    session = session_manager.get_or_create(user_id)

    # Capacity guard
    if len(session.files) >= settings.MAX_FILES_PER_USER:
        await message.reply(
            f"⚠️ Queue is full ({settings.MAX_FILES_PER_USER} files max).\n"
            "Run /zip to package the current batch or /clear to start over."
        )
        return

    # Duplicate guard — skip files with the same unique ID
    existing_ids = {f.file_unique_id for f in session.files}
    if entry.file_unique_id in existing_ids:
        await message.reply(
            f"↩️ <b>Already queued:</b> <code>{entry.display_name}</code>"
        )
        return

    # Deduplicate display names within the session
    entry.display_name = _unique_name(entry.display_name, session.files)
    session.add(entry)

    total = len(session.files)
    size_hint = f" · {_fmt_size(entry.file_size)}" if entry.file_size else ""
    await message.reply(
        f"✅ <b>Added:</b> <code>{entry.display_name}</code>{size_hint}\n"
        f"📦 Total queued: <b>{total}</b> file(s)\n\n"
        "Send /zip when ready to download & package."
    )
    logger.info(
        "User %s queued '%s' (total=%d)", user_id, entry.display_name, total
    )


def _unique_name(name: str, existing: list[FileEntry]) -> str:
    """Append a counter suffix if the display name is already taken."""
    taken = {f.display_name for f in existing}
    if name not in taken:
        return name

    stem, _, ext = name.rpartition(".")
    if not stem:
        stem, ext = name, ""
    else:
        ext = "." + ext

    counter = 2
    while True:
        candidate = f"{stem} ({counter}){ext}"
        if candidate not in taken:
            return candidate
        counter += 1


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"
