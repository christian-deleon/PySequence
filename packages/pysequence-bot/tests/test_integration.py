"""Integration tests that hit the real Sequence API via the SDK.

These are gated behind the 'integration' marker and excluded by default.
Run them explicitly with:

    poetry run pytest -m integration
"""

import pytest


pytestmark = pytest.mark.integration


def _make_client():
    from pysequence_sdk import SequenceClient, get_access_token
    from pysequence_bot.config import get_sdk_config

    cfg = get_sdk_config()
    return SequenceClient(get_access_token(), token_provider=get_access_token), cfg


def test_get_pods_returns_data() -> None:
    """Fetch pods from the SDK."""
    client, _ = _make_client()
    pods = client.get_pods()

    assert isinstance(pods, list)
    assert len(pods) > 0
    for pod in pods:
        assert "id" in pod
        assert "name" in pod
        assert "balance" in pod
        assert "balance_cents" in pod


def test_get_pod_balance_finds_a_pod() -> None:
    """Fetch a specific pod by name (picks the first one from get_pods)."""
    client, _ = _make_client()
    pods = client.get_pods()
    assert len(pods) > 0

    first_name = pods[0]["name"]
    result = client.get_pod_balance(first_name)

    assert result is not None
    assert result["name"] == first_name


def test_get_pod_detail() -> None:
    """Fetch detailed info for a pod."""
    client, cfg = _make_client()
    pods = client.get_pods()
    assert len(pods) > 0

    pod = pods[0]
    detail = client.get_pod_detail(cfg.org_id, pod["id"])

    assert "id" in detail
    assert "name" in detail


def test_get_total_balance() -> None:
    """Fetch total balance across all pods."""
    client, _ = _make_client()
    result = client.get_total_balance()

    assert "total_balance_cents" in result
    assert "total_balance" in result
    assert "pod_count" in result
    assert isinstance(result["total_balance_cents"], int)
    assert result["pod_count"] > 0


def test_get_activity_summary() -> None:
    """Fetch monthly activity summary."""
    client, _ = _make_client()
    result = client.get_activity_summary()

    assert "transfer_count" in result
    assert "rule_executions" in result
    assert "total_incoming_cents" in result
    assert "total_incoming" in result
    assert isinstance(result["transfer_count"], int)
    assert isinstance(result["rule_executions"], int)


def test_get_activity() -> None:
    """Fetch recent transfer activity."""
    client, cfg = _make_client()
    result = client.get_activity(cfg.org_id, first=5)

    assert "transfers" in result
    assert "page_info" in result
    assert isinstance(result["transfers"], list)
    assert "end_cursor" in result["page_info"]
    assert "has_next_page" in result["page_info"]

    for t in result["transfers"]:
        assert "id" in t
        assert "status" in t
        assert "amount" in t
        assert "amount_cents" in t
        assert "source" in t
        assert "destination" in t
        assert "direction" in t
        assert "activity_type" in t


def test_get_activity_with_filters() -> None:
    """Fetch activity with status filter."""
    client, cfg = _make_client()
    result = client.get_activity(cfg.org_id, first=5, statuses=["COMPLETE"])

    assert isinstance(result["transfers"], list)
    for t in result["transfers"]:
        assert t["status"] == "COMPLETE"


def test_get_transfer_detail() -> None:
    """Fetch detail for a specific transfer (uses first transfer from activity)."""
    client, cfg = _make_client()
    activity = client.get_activity(cfg.org_id, first=1)
    assert len(activity["transfers"]) > 0, "No transfers to test against"

    transfer_id = activity["transfers"][0]["id"]
    detail = client.get_transfer_detail(cfg.org_id, transfer_id)

    assert detail["id"] == transfer_id
    assert "status" in detail
    assert "amount" in detail
    assert "amount_cents" in detail
    assert "source" in detail
    assert "destination" in detail
    assert "direction" in detail
    assert "activity_type" in detail


def test_get_all_accounts() -> None:
    """Fetch all account types: pods, ports, and external accounts."""
    client, cfg = _make_client()
    result = client.get_all_accounts(cfg.org_id)

    assert "pods" in result
    assert "ports" in result
    assert "accounts" in result
    assert isinstance(result["pods"], list)
    assert isinstance(result["ports"], list)
    assert isinstance(result["accounts"], list)

    assert len(result["pods"]) > 0
    for pod in result["pods"]:
        assert "id" in pod
        assert "name" in pod
        assert "balance" in pod
        assert "balance_cents" in pod

    for port in result["ports"]:
        assert "id" in port
        assert "name" in port
        assert "balance" in port

    for account in result["accounts"]:
        assert "id" in account
        assert "name" in account
        assert "balance" in account
