"""Global daily cumulative transfer limit tracker.

JSON-backed store that tracks the global daily transfer total
to prevent excessive transfers from draining accounts.
"""

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


log = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("SEQUENCE_DATA_DIR", "."))
DEFAULT_PATH = DATA_DIR / ".daily_limits.json"


class DailyLimitTracker:
    """Track global daily transfer totals with JSON persistence."""

    def __init__(
        self, path: Path = DEFAULT_PATH, max_daily_cents: int = 2_500_000
    ) -> None:
        self._path = path
        self._max_daily_cents = max_daily_cents
        self._records: dict[str, Any] = self._load()
        self._prune_old()

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        
        try:
            return json.loads(self._path.read_text())
        
        except (json.JSONDecodeError, TypeError):
            log.warning("Corrupt daily limits file at %s, starting fresh", self._path)
            return {}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._records, indent=2) + "\n")

    def _prune_old(self) -> None:
        cutoff = (date.today() - timedelta(days=2)).isoformat()
        keys_to_remove = [k for k in self._records if k < cutoff]

        for k in keys_to_remove:
            del self._records[k]

        if keys_to_remove:
            self._save()

    def _today_key(self) -> str:
        return date.today().isoformat()

    def _total_today(self) -> int:
        today = self._today_key()
        entries = self._records.get(today, [])

        return sum(e["amount_cents"] for e in entries)

    def check(self, amount_cents: int) -> tuple[bool, int]:
        """Check if a transfer is within the daily limit.

        Returns (allowed, remaining_cents).
        """

        used = self._total_today()
        remaining = self._max_daily_cents - used

        return (amount_cents <= remaining, remaining)

    def record(self, amount_cents: int, transfer_id: str) -> None:
        """Record a completed transfer against the daily limit."""
        today = self._today_key()

        if today not in self._records:
            self._records[today] = []

        self._records[today].append(
            {
                "transfer_id": transfer_id,
                "amount_cents": amount_cents,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        self._save()
        
        log.info("Recorded transfer %s: %d cents", transfer_id, amount_cents)
