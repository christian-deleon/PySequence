"""Unit tests for pysequence_api.safeguards."""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from pysequence_api.safeguards import AuditLog, DailyLimitTracker


class TestDailyLimitTracker:
    def test_allows_within_limit(self, tmp_path: Path) -> None:
        tracker = DailyLimitTracker(
            path=tmp_path / "limits.json", max_daily_cents=10000
        )
        allowed, remaining = tracker.check(5000)
        assert allowed is True
        assert remaining == 10000

    def test_records_and_reduces_remaining(self, tmp_path: Path) -> None:
        tracker = DailyLimitTracker(
            path=tmp_path / "limits.json", max_daily_cents=10000
        )
        tracker.record(3000, "t-1")
        allowed, remaining = tracker.check(5000)
        assert allowed is True
        assert remaining == 7000

    def test_rejects_over_limit(self, tmp_path: Path) -> None:
        tracker = DailyLimitTracker(
            path=tmp_path / "limits.json", max_daily_cents=10000
        )
        tracker.record(8000, "t-1")
        allowed, remaining = tracker.check(5000)
        assert allowed is False
        assert remaining == 2000

    def test_rejects_exactly_over(self, tmp_path: Path) -> None:
        tracker = DailyLimitTracker(
            path=tmp_path / "limits.json", max_daily_cents=10000
        )
        tracker.record(10000, "t-1")
        allowed, remaining = tracker.check(1)
        assert allowed is False
        assert remaining == 0

    def test_allows_exactly_at_limit(self, tmp_path: Path) -> None:
        tracker = DailyLimitTracker(
            path=tmp_path / "limits.json", max_daily_cents=10000
        )
        tracker.record(5000, "t-1")
        allowed, remaining = tracker.check(5000)
        assert allowed is True
        assert remaining == 5000

    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        path = tmp_path / "limits.json"
        t1 = DailyLimitTracker(path=path, max_daily_cents=10000)
        t1.record(6000, "t-1")

        t2 = DailyLimitTracker(path=path, max_daily_cents=10000)
        allowed, remaining = t2.check(5000)
        assert allowed is False
        assert remaining == 4000

    def test_prunes_old_records(self, tmp_path: Path) -> None:
        path = tmp_path / "limits.json"
        old_date = (date.today() - timedelta(days=3)).isoformat()
        data = {
            old_date: [{"transfer_id": "old", "amount_cents": 9999, "timestamp": "t"}]
        }
        path.write_text(json.dumps(data))

        tracker = DailyLimitTracker(path=path, max_daily_cents=10000)
        allowed, remaining = tracker.check(10000)
        assert allowed is True
        assert remaining == 10000

    def test_handles_corrupt_file(self, tmp_path: Path) -> None:
        path = tmp_path / "limits.json"
        path.write_text("not json")

        tracker = DailyLimitTracker(path=path, max_daily_cents=10000)
        allowed, remaining = tracker.check(5000)
        assert allowed is True

    def test_handles_missing_file(self, tmp_path: Path) -> None:
        tracker = DailyLimitTracker(
            path=tmp_path / "nonexistent.json", max_daily_cents=10000
        )
        allowed, remaining = tracker.check(5000)
        assert allowed is True


class TestAuditLog:
    def test_writes_event(self, tmp_path: Path) -> None:
        path = tmp_path / "audit.jsonl"
        audit = AuditLog(path=path)
        audit.log("transfer_requested", transfer_id="t-1", amount_cents=5000)

        lines = path.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["event_type"] == "transfer_requested"
        assert entry["transfer_id"] == "t-1"
        assert entry["amount_cents"] == 5000
        assert "timestamp" in entry

    def test_appends_multiple_events(self, tmp_path: Path) -> None:
        path = tmp_path / "audit.jsonl"
        audit = AuditLog(path=path)
        audit.log("transfer_requested", transfer_id="t-1")
        audit.log("transfer_completed", transfer_id="t-1")

        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["event_type"] == "transfer_requested"
        assert json.loads(lines[1])["event_type"] == "transfer_completed"

    def test_optional_fields_omitted_when_none(self, tmp_path: Path) -> None:
        path = tmp_path / "audit.jsonl"
        audit = AuditLog(path=path)
        audit.log("transfer_failed", error="timeout")

        entry = json.loads(path.read_text().strip())
        assert entry["event_type"] == "transfer_failed"
        assert entry["error"] == "timeout"
        assert "transfer_id" not in entry
        assert "amount_cents" not in entry

    def test_includes_all_fields(self, tmp_path: Path) -> None:
        path = tmp_path / "audit.jsonl"
        audit = AuditLog(path=path)
        audit.log(
            "transfer_completed",
            transfer_id="t-1",
            amount_cents=5000,
            source="pod-1",
            destination="pod-2",
            note="test transfer",
        )

        entry = json.loads(path.read_text().strip())
        assert entry["source"] == "pod-1"
        assert entry["destination"] == "pod-2"
        assert entry["note"] == "test transfer"
