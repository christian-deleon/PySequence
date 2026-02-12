"""Unit tests for pysequence_sdk.safeguards."""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from pysequence_sdk.safeguards import AuditLog, DailyLimitTracker

# -- DailyLimitTracker: global mode (no user_id) ----------------------------


class TestDailyLimitTrackerGlobal:
    """Tests using the global (no user_id) interface — backwards-compatible
    with the original API server call sites."""

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


# -- DailyLimitTracker: per-user mode ---------------------------------------


class TestDailyLimitTrackerPerUser:
    """Tests using the per-user (user_id=...) interface."""

    def test_allows_within_limit(self, tmp_path: Path) -> None:
        tracker = DailyLimitTracker(
            path=tmp_path / "limits.json", max_daily_cents=100_000
        )
        allowed, remaining = tracker.check(50_000, user_id=12345)
        assert allowed is True
        assert remaining == 100_000

    def test_blocks_over_limit(self, tmp_path: Path) -> None:
        tracker = DailyLimitTracker(
            path=tmp_path / "limits.json", max_daily_cents=100_000
        )
        tracker.record(80_000, "txn-1", user_id=12345)
        allowed, remaining = tracker.check(30_000, user_id=12345)
        assert allowed is False
        assert remaining == 20_000

    def test_separate_users(self, tmp_path: Path) -> None:
        tracker = DailyLimitTracker(
            path=tmp_path / "limits.json", max_daily_cents=100_000
        )
        tracker.record(90_000, "txn-1", user_id=12345)
        # User 12345 blocked
        allowed, _ = tracker.check(20_000, user_id=12345)
        assert allowed is False
        # User 67890 allowed
        allowed, remaining = tracker.check(20_000, user_id=67890)
        assert allowed is True
        assert remaining == 100_000

    def test_resets_next_day(self, tmp_path: Path) -> None:
        tracker = DailyLimitTracker(
            path=tmp_path / "limits.json", max_daily_cents=100_000
        )
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        tracker._records[yesterday] = {
            "12345": [{"transfer_id": "old", "amount_cents": 90_000, "timestamp": "t"}]
        }
        tracker._save()

        allowed, remaining = tracker.check(50_000, user_id=12345)
        assert allowed is True
        assert remaining == 100_000

    def test_persistence(self, tmp_path: Path) -> None:
        path = tmp_path / "limits.json"
        tracker1 = DailyLimitTracker(path=path, max_daily_cents=100_000)
        tracker1.record(60_000, "txn-1", user_id=12345)

        tracker2 = DailyLimitTracker(path=path, max_daily_cents=100_000)
        allowed, remaining = tracker2.check(50_000, user_id=12345)
        assert allowed is False
        assert remaining == 40_000

    def test_prune_old_records(self, tmp_path: Path) -> None:
        tracker = DailyLimitTracker(
            path=tmp_path / "limits.json", max_daily_cents=100_000
        )
        old_date = (date.today() - timedelta(days=3)).isoformat()
        tracker._records[old_date] = {
            "12345": [{"transfer_id": "old", "amount_cents": 50_000, "timestamp": "t"}]
        }
        tracker._save()

        tracker2 = DailyLimitTracker(
            path=tmp_path / "limits.json", max_daily_cents=100_000
        )
        assert old_date not in tracker2._records


# -- DailyLimitTracker: migration -------------------------------------------


class TestDailyLimitTrackerMigration:
    """Test migration from flat-list (old API) format to nested-dict format."""

    def test_migrates_flat_list_format(self, tmp_path: Path) -> None:
        path = tmp_path / "limits.json"
        today = date.today().isoformat()
        old_format = {
            today: [{"transfer_id": "t-1", "amount_cents": 3000, "timestamp": "t"}]
        }
        path.write_text(json.dumps(old_format))

        tracker = DailyLimitTracker(path=path, max_daily_cents=10000)
        # Should have migrated and still count the old record
        allowed, remaining = tracker.check(5000)
        assert allowed is True
        assert remaining == 7000

    def test_prunes_old_flat_list(self, tmp_path: Path) -> None:
        path = tmp_path / "limits.json"
        old_date = (date.today() - timedelta(days=3)).isoformat()
        old_format = {
            old_date: [{"transfer_id": "old", "amount_cents": 9999, "timestamp": "t"}]
        }
        path.write_text(json.dumps(old_format))

        tracker = DailyLimitTracker(path=path, max_daily_cents=10000)
        allowed, remaining = tracker.check(10000)
        assert allowed is True
        assert remaining == 10000


# -- AuditLog: basic (no user fields) ---------------------------------------


class TestAuditLogBasic:
    """Tests using the basic (no user_id) interface — backwards-compatible
    with the original API server call sites."""

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
        assert "user_id" not in entry

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


# -- AuditLog: with user fields ---------------------------------------------


class TestAuditLogWithUser:
    """Tests for the per-user audit fields (user_id, user_name)."""

    def test_log_creates_file(self, tmp_path: Path) -> None:
        path = tmp_path / "audit.jsonl"
        audit = AuditLog(path=path)
        audit.log("transfer_staged", user_id=12345, transfer_id="txn-1")
        assert path.exists()

    def test_append_only(self, tmp_path: Path) -> None:
        path = tmp_path / "audit.jsonl"
        audit = AuditLog(path=path)
        audit.log("transfer_staged", user_id=12345, transfer_id="txn-1")
        audit.log("transfer_confirmed", user_id=12345, transfer_id="txn-1")
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_log_format_with_user(self, tmp_path: Path) -> None:
        path = tmp_path / "audit.jsonl"
        audit = AuditLog(path=path)
        audit.log(
            "transfer_staged",
            user_id=12345,
            user_name="Alice",
            transfer_id="txn-1",
            amount_cents=5000,
            source="Rent",
            destination="Groceries",
            note="Test",
        )
        line = path.read_text().strip()
        entry = json.loads(line)
        assert entry["event_type"] == "transfer_staged"
        assert entry["user_id"] == 12345
        assert entry["user_name"] == "Alice"
        assert entry["transfer_id"] == "txn-1"
        assert entry["amount_cents"] == 5000
        assert entry["source"] == "Rent"
        assert entry["destination"] == "Groceries"
        assert entry["note"] == "Test"
        assert "timestamp" in entry
