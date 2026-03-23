"""
ZIP creation service.

Uses ZIP_STORED (no compression) to preserve files byte-for-byte.
Automatically splits the archive into multiple parts if the total size
would exceed Telegram's upload limit.
"""

from __future__ import annotations

import logging
import time
import zipfile
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Type alias: list of (local_path, archive_filename) pairs
FilePairList = List[Tuple[Path, str]]


class ZipService:
    def __init__(self, temp_dir: Path) -> None:
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ─────────────────────────────────────────────────────────────

    def create_zip(
        self,
        files: FilePairList,
        prefix: str = "Playlist",
        size_limit: int = 2 * 1024 ** 3,
    ) -> List[Path]:
        """
        Pack *files* into one or more ZIP archives (ZIP_STORED).

        Returns a list of Path objects pointing to the created archives.
        Raises on critical errors.
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        folder_name = f"{prefix}_{timestamp}"

        # Estimate total uncompressed size to decide splitting strategy
        total_bytes = sum(p.stat().st_size for p, _ in files if p.exists())
        logger.info(
            "Creating ZIP: %d file(s), ~%.1f MB total, limit=%.1f MB",
            len(files),
            total_bytes / 1024 ** 2,
            size_limit / 1024 ** 2,
        )

        if total_bytes <= size_limit:
            # Single archive
            zip_path = self._build_zip(
                files=files,
                zip_name=f"{folder_name}.zip",
                folder_name=folder_name,
            )
            return [zip_path]
        else:
            # Multi-part split
            return self._build_split_zips(
                files=files,
                folder_name=folder_name,
                size_limit=size_limit,
            )

    def cleanup(self, paths: List[Path]) -> None:
        """Delete ZIP files after they have been sent."""
        for p in paths:
            try:
                p.unlink(missing_ok=True)
                logger.debug("Deleted ZIP: %s", p)
            except Exception as exc:
                logger.warning("Could not delete %s: %s", p, exc)

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _build_zip(
        self,
        files: FilePairList,
        zip_name: str,
        folder_name: str,
    ) -> Path:
        zip_path = self.temp_dir / zip_name
        with zipfile.ZipFile(
            zip_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True
        ) as zf:
            for local_path, archive_name in files:
                if not local_path.exists():
                    logger.warning("Skipping missing file: %s", local_path)
                    continue
                arcname = f"{folder_name}/{archive_name}"
                zf.write(local_path, arcname=arcname)
                logger.debug("Added to ZIP: %s → %s", local_path.name, arcname)

        logger.info("ZIP created: %s (%.1f MB)", zip_path.name, zip_path.stat().st_size / 1024 ** 2)
        return zip_path

    def _build_split_zips(
        self,
        files: FilePairList,
        folder_name: str,
        size_limit: int,
    ) -> List[Path]:
        """Greedily pack files into parts that each stay under size_limit."""
        parts: List[List[Tuple[Path, str]]] = []
        current_part: List[Tuple[Path, str]] = []
        current_size = 0

        for local_path, archive_name in files:
            try:
                file_size = local_path.stat().st_size
            except FileNotFoundError:
                logger.warning("Skipping missing file: %s", local_path)
                continue

            # If a single file exceeds the limit, it still goes in its own part
            if file_size > size_limit:
                logger.warning(
                    "File '%s' (%.1f MB) exceeds Telegram limit — "
                    "placing it in its own part anyway.",
                    archive_name,
                    file_size / 1024 ** 2,
                )

            if current_size + file_size > size_limit and current_part:
                parts.append(current_part)
                current_part = []
                current_size = 0

            current_part.append((local_path, archive_name))
            current_size += file_size

        if current_part:
            parts.append(current_part)

        zip_paths: List[Path] = []
        for i, part_files in enumerate(parts, 1):
            zip_path = self._build_zip(
                files=part_files,
                zip_name=f"{folder_name}_part{i}.zip",
                folder_name=folder_name,
            )
            zip_paths.append(zip_path)

        return zip_paths
