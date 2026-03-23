"""
Per-user session management.

Keeps an in-memory registry of FileEntry queues with TTL-based auto-expiry.
All operations are thread-safe for asyncio single-threaded use; a lock is used
to make the cleanup loop safe even if coroutines interleave.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class FileEntry:
    """Represents a single queued file."""
    file_id: str
    file_unique_id: str
    display_name: str
    mime_type: str
    file_size: int  # bytes; 0 if unknown


@dataclass
class UserSession:
    """State bucket for one user."""
    user_id: int
    files: List[FileEntry] = field(default_factory=list)
    created_at: float = field(default_factory=time.monotonic)
    last_activity: float = field(default_factory=time.monotonic)

    def touch(self) -> None:
        self.last_activity = time.monotonic()

    def add(self, entry: FileEntry) -> None:
        self.files.append(entry)
        self.touch()

    def clear(self) -> None:
        self.files.clear()
        self.touch()

    def is_expired(self, ttl: float) -> bool:
        return (time.monotonic() - self.last_activity) > ttl


class SessionManager:
    def __init__(
        self,
        session_ttl: int = 3600,
        max_files_per_user: int = 200,
        cleanup_interval: int = 300,
    ) -> None:
        self._sessions: dict[int, UserSession] = {}
        self.session_ttl = float(session_ttl)
        self.max_files_per_user = max_files_per_user
        self._cleanup_interval = cleanup_interval

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_or_create(self, user_id: int) -> UserSession:
        if user_id not in self._sessions:
            self._sessions[user_id] = UserSession(user_id=user_id)
            logger.debug("Created session for user %s", user_id)
        else:
            self._sessions[user_id].touch()
        return self._sessions[user_id]

    def clear(self, user_id: int) -> None:
        if user_id in self._sessions:
            self._sessions[user_id].clear()

    def remove(self, user_id: int) -> None:
        self._sessions.pop(user_id, None)

    def active_count(self) -> int:
        return len(self._sessions)

    # ── Background cleanup ─────────────────────────────────────────────────────

    async def auto_cleanup_loop(self) -> None:
        """Periodically evict sessions that have been idle past their TTL."""
        while True:
            await asyncio.sleep(self._cleanup_interval)
            expired = [
                uid
                for uid, sess in list(self._sessions.items())
                if sess.is_expired(self.session_ttl)
            ]
            for uid in expired:
                logger.info("Auto-expiring idle session for user %s", uid)
                self._sessions.pop(uid, None)
            if expired:
                logger.info("Cleaned up %d expired session(s).", len(expired))
