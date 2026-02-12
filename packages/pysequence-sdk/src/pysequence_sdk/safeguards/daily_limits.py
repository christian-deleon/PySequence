"""Daily cumulative transfer limit tracker.

JSON-backed store that tracks daily transfer totals (optionally per-user)
to prevent excessive transfers from draining accounts.

When ``user_id`` is omitted (or ``None``), a ``"__global__"`` key is used
so the API server's existing call sites work unchanged.  When a ``user_id``
is provided, limits are tracked per-user.  Storage always uses nested-dict
format: ``records[today][user_key] = [...]``.
"""

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pysequence_sdk.config import DATA_DIR

log = logging.getLogger(__name__)

DEFAULT_PATH = DATA_DIR / ".daily_limits.json"

_GLOBAL_KEY = "__global__"


class DailyLimitTracker:
    """Track daily transfer totals with JSON persistence."""

    def __init__(
        self, path: Path = DEFAULT_PATH, max_daily_cents: int = 2_500_000
    ) -> None:
        self._path = path
        self._max_daily_cents = max_daily_cents
        self._records: dict[str, Any] = self._load()
        self._migrate()
        self._prune_old()

    def _load(self) -> dict[str, Any]:
        """Load records from disk. Returns empty dict if missing or corrupt."""
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text())
        except (json.JSONDecodeError, TypeError):
            log.warning("Corrupt daily limits file at %s, starting fresh", self._path)
            return {}

    def _migrate(self) -> None:
        """Migrate flat-list format to nested-dict format.

        Old API format stored ``records[date] = [entries...]``.
        New format stores ``records[date][user_key] = [entries...]``.
        """
        migrated = False
        for day_key, value in list(self._records.items()):
            if isinstance(value, list):
                self._records[day_key] = {_GLOBAL_KEY: value}
                migrated = True
        if migrated:
            self._save()

    def _save(self) -> None:
        """Write records to disk."""
        self._path.write_text(json.dumps(self._records, indent=2) + "\n")

    def _prune_old(self) -> None:
        """Remove records older than 2 days."""
        cutoff = (date.today() - timedelta(days=2)).isoformat()
        keys_to_remove = [k for k in self._records if k < cutoff]
        for k in keys_to_remove:
            del self._records[k]
        if keys_to_remove:
            self._save()

    def _today_key(self) -> str:
        """Return today's date as an ISO string."""
        return date.today().isoformat()

    @staticmethod
    def _user_key(user_id: int | None) -> str:
        return str(user_id) if user_id is not None else _GLOBAL_KEY

    def _total_today(self, user_key: str) -> int:
        """Get total cents transferred for a user key today."""
        today = self._today_key()
        if today not in self._records:
            return 0
        entries = self._records[today].get(user_key, [])
        return sum(e["amount_cents"] for e in entries)

    def check(
        self, amount_cents: int, *, user_id: int | None = None
    ) -> tuple[bool, int]:
        """Check if a transfer is within the daily limit.

        Returns (allowed, remaining_cents).
        """
        user_key = self._user_key(user_id)
        used = self._total_today(user_key)
        remaining = self._max_daily_cents - used
        return (amount_cents <= remaining, remaining)

    def record(
        self, amount_cents: int, transfer_id: str, *, user_id: int | None = None
    ) -> None:
        """Record a completed transfer against the daily limit."""
        today = self._today_key()
        user_key = self._user_key(user_id)

        if today not in self._records:
            self._records[today] = {}
        if user_key not in self._records[today]:
            self._records[today][user_key] = []

        self._records[today][user_key].append(
            {
                "transfer_id": transfer_id,
                "amount_cents": amount_cents,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._save()
        log.info(
            "Recorded transfer %s for %s: %d cents",
            transfer_id,
            user_key,
            amount_cents,
        )
