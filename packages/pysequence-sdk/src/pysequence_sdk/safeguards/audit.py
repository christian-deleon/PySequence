"""Append-only audit trail for financial operations.

Writes one JSON line per event to an immutable JSONL file.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pysequence_sdk.config import DATA_DIR

log = logging.getLogger(__name__)

DEFAULT_PATH = DATA_DIR / ".audit.jsonl"


class AuditLog:
    """Append-only JSONL audit logger for transfer operations."""

    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self._path = path

    def log(
        self,
        event_type: str,
        *,
        user_id: int | None = None,
        user_name: str | None = None,
        transfer_id: str | None = None,
        amount_cents: int | None = None,
        source: str | None = None,
        destination: str | None = None,
        note: str | None = None,
        error: str | None = None,
    ) -> None:
        """Write a single audit event as a JSON line."""
        entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
        }
        if user_id is not None:
            entry["user_id"] = user_id
        if user_name is not None:
            entry["user_name"] = user_name
        if transfer_id is not None:
            entry["transfer_id"] = transfer_id
        if amount_cents is not None:
            entry["amount_cents"] = amount_cents
        if source is not None:
            entry["source"] = source
        if destination is not None:
            entry["destination"] = destination
        if note is not None:
            entry["note"] = note
        if error is not None:
            entry["error"] = error

        with open(self._path, "a") as f:
            f.write(json.dumps(entry) + "\n")

        log.info("Audit: %s transfer_id=%s user=%s", event_type, transfer_id, user_id)
