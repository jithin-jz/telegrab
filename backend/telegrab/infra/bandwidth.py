"""Daily bandwidth tracker.

Persisted to `config.paths.bandwidth_path()`; resets at local midnight and
enforces a fixed 200 GB/day soft cap on transfers.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass
from datetime import date

from ..config import bandwidth_path

log = logging.getLogger(__name__)

DAILY_LIMIT_BYTES = 200 * 1024 * 1024 * 1024  # 200 GB
_UNITS = ("B", "KB", "MB", "GB", "TB")


@dataclass
class BandwidthStats:
    date: str
    up_bytes: int = 0
    down_bytes: int = 0


def _today() -> str:
    return date.today().isoformat()


class BandwidthManager:
    """Thread-safe bandwidth bookkeeping with on-disk persistence."""

    _SAVE_INTERVAL = 5.0  # seconds between disk writes

    def __init__(self) -> None:
        self._path = bandwidth_path()
        self._lock = threading.Lock()
        self._stats = self._load()
        self._dirty = False
        self._last_save = 0.0

    def _load(self) -> BandwidthStats:
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            return BandwidthStats(
                date=data.get("date", _today()),
                up_bytes=int(data.get("up_bytes", 0)),
                down_bytes=int(data.get("down_bytes", 0)),
            )
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return BandwidthStats(date=_today())

    def _save_if_needed(self) -> None:
        import time as _time
        now = _time.monotonic()
        if not self._dirty:
            return
        if now - self._last_save < self._SAVE_INTERVAL:
            return
        self._flush_locked()

    def _flush_locked(self) -> None:
        import time as _time
        try:
            with self._path.open("w", encoding="utf-8") as fh:
                json.dump(asdict(self._stats), fh)
            self._dirty = False
            self._last_save = _time.monotonic()
        except OSError as exc:
            log.warning("Bandwidth save failed: %s", exc)

    def _check_reset_locked(self) -> None:
        today = _today()
        if self._stats.date != today:
            log.info("Bandwidth reset (old=%s, new=%s)", self._stats.date, today)
            self._stats = BandwidthStats(date=today)
            self._dirty = True
            self._flush_locked()

    def can_transfer(self, bytes_count: int) -> tuple[bool, str | None]:
        with self._lock:
            self._check_reset_locked()
            total = self._stats.up_bytes + self._stats.down_bytes + bytes_count
            if total > DAILY_LIMIT_BYTES:
                return False, (
                    f"Daily bandwidth limit ({_format(DAILY_LIMIT_BYTES)}) "
                    f"exceeded! Used: {_format(total)}"
                )
            return True, None

    def add_up(self, bytes_count: int) -> None:
        with self._lock:
            self._check_reset_locked()
            self._stats.up_bytes += bytes_count
            self._dirty = True
            self._save_if_needed()

    def add_down(self, bytes_count: int) -> None:
        with self._lock:
            self._check_reset_locked()
            self._stats.down_bytes += bytes_count
            self._dirty = True
            self._save_if_needed()

    def flush(self) -> None:
        """Force a save (call on shutdown)."""
        with self._lock:
            if self._dirty:
                self._flush_locked()

    def get_stats(self) -> dict:
        with self._lock:
            self._check_reset_locked()
            return asdict(self._stats)


def _format(bytes_count: int) -> str:
    v = float(bytes_count)
    i = 0
    while v >= 1024.0 and i < len(_UNITS) - 1:
        v /= 1024.0
        i += 1
    return f"{v:.2f} {_UNITS[i]}"


_manager: BandwidthManager | None = None


def get_manager() -> BandwidthManager:
    global _manager
    if _manager is None:
        _manager = BandwidthManager()
    return _manager
