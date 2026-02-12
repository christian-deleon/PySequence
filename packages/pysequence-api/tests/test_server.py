"""Unit tests for pysequence_api server."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pysequence_api.routes import health_router, router
from pysequence_api.safeguards import AuditLog, DailyLimitTracker

API_KEY = "test-api-key"


def _build_app(
    mock_client: MagicMock,
    tmp_path: Path,
    max_transfer_cents: int = 1_000_000,
    max_daily_transfer_cents: int = 2_500_000,
) -> FastAPI:
    """Build a test app with mocked dependencies."""

    from pysequence_api.config import ServerConfig

    app = FastAPI()

    config = ServerConfig(
        api_key=API_KEY,
        org_id="org-1",
        kyc_id="kyc-1",
        max_transfer_cents=max_transfer_cents,
        max_daily_transfer_cents=max_daily_transfer_cents,
    )
    app.state.server_config = config
    app.state.api_key = API_KEY
    app.state.client = mock_client
    app.state.daily_limits = DailyLimitTracker(
        path=tmp_path / "limits.json",
        max_daily_cents=max_daily_transfer_cents,
    )
    app.state.audit = AuditLog(path=tmp_path / "audit.jsonl")

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=502, content={"detail": str(exc)})

    app.include_router(health_router)
    app.include_router(router)

    return app


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def app(mock_client: MagicMock, tmp_path: Path) -> FastAPI:
    return _build_app(mock_client, tmp_path)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _auth_headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY}


class TestAuth:
    def test_rejects_missing_api_key(self, client: TestClient) -> None:
        resp = client.get("/api/pods")
        assert resp.status_code == 422

    def test_rejects_invalid_api_key(self, client: TestClient) -> None:
        resp = client.get("/api/pods", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401

    def test_accepts_valid_api_key(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.get_pods.return_value = []
        resp = client.get("/api/pods", headers=_auth_headers())
        assert resp.status_code == 200


class TestHealth:
    def test_health_no_auth(self, client: TestClient) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestPods:
    def test_list_pods(self, client: TestClient, mock_client: MagicMock) -> None:
        mock_client.get_pods.return_value = [
            {"id": "p1", "name": "Groceries", "balance_cents": 5000}
        ]
        resp = client.get("/api/pods", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Groceries"

    def test_total_balance(self, client: TestClient, mock_client: MagicMock) -> None:
        mock_client.get_total_balance.return_value = {
            "total_balance_cents": 10000,
            "total_balance": "$100.00",
            "pod_count": 2,
        }
        resp = client.get("/api/pods/balance", headers=_auth_headers())
        assert resp.status_code == 200
        assert resp.json()["total_balance_cents"] == 10000

    def test_pod_balance_found(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.get_pod_balance.return_value = {
            "id": "p1",
            "name": "Groceries",
            "balance_cents": 5000,
        }
        resp = client.get("/api/pods/Groceries/balance", headers=_auth_headers())
        assert resp.status_code == 200
        assert resp.json()["name"] == "Groceries"

    def test_pod_balance_not_found(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.get_pod_balance.return_value = None
        resp = client.get("/api/pods/Nonexistent/balance", headers=_auth_headers())
        assert resp.status_code == 404

    def test_pod_detail(self, client: TestClient, mock_client: MagicMock) -> None:
        mock_client.get_pod_detail.return_value = {"id": "p1", "name": "Groceries"}
        resp = client.get("/api/pods/org-1/pod-1", headers=_auth_headers())
        assert resp.status_code == 200
        assert resp.json()["id"] == "p1"

    def test_pod_detail_by_id_uses_server_org_id(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.get_pod_detail.return_value = {"id": "p1", "name": "Groceries"}
        resp = client.get("/api/pods/detail/pod-1", headers=_auth_headers())
        assert resp.status_code == 200
        mock_client.get_pod_detail.assert_called_once_with("org-1", "pod-1")


class TestAccounts:
    def test_list_accounts(self, client: TestClient, mock_client: MagicMock) -> None:
        mock_client.get_all_accounts.return_value = {
            "pods": [],
            "ports": [],
            "accounts": [],
        }
        resp = client.get("/api/accounts", headers=_auth_headers())
        assert resp.status_code == 200
        mock_client.get_all_accounts.assert_called_once_with(org_id="org-1")

    def test_list_accounts_explicit_org_id(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.get_all_accounts.return_value = {
            "pods": [],
            "ports": [],
            "accounts": [],
        }
        resp = client.get(
            "/api/accounts", params={"org_id": "org-2"}, headers=_auth_headers()
        )
        assert resp.status_code == 200
        mock_client.get_all_accounts.assert_called_once_with(org_id="org-2")


class TestActivity:
    def test_activity_summary(self, client: TestClient, mock_client: MagicMock) -> None:
        mock_client.get_activity_summary.return_value = {
            "transfer_count": 5,
            "rule_executions": 2,
            "total_incoming_cents": 50000,
            "total_incoming": "$500.00",
        }
        resp = client.get("/api/activity/summary", headers=_auth_headers())
        assert resp.status_code == 200
        assert resp.json()["transfer_count"] == 5

    def test_list_activity_defaults_org_id(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.get_activity.return_value = {
            "transfers": [],
            "page_info": {"end_cursor": "", "has_next_page": False},
        }
        resp = client.get("/api/activity", headers=_auth_headers())
        assert resp.status_code == 200
        mock_client.get_activity.assert_called_once_with(
            org_id="org-1",
            first=10,
            after="",
            statuses=None,
            directions=None,
            activity_types=None,
        )

    def test_list_activity_explicit_org_id(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.get_activity.return_value = {
            "transfers": [],
            "page_info": {"end_cursor": "", "has_next_page": False},
        }
        resp = client.get(
            "/api/activity", params={"org_id": "org-2"}, headers=_auth_headers()
        )
        assert resp.status_code == 200
        mock_client.get_activity.assert_called_once_with(
            org_id="org-2",
            first=10,
            after="",
            statuses=None,
            directions=None,
            activity_types=None,
        )

    def test_list_activity_with_filters(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.get_activity.return_value = {
            "transfers": [],
            "page_info": {"end_cursor": "", "has_next_page": False},
        }
        resp = client.get(
            "/api/activity",
            params={
                "statuses": "COMPLETE,PENDING",
                "directions": "INTERNAL",
                "activity_types": "ONE_TIME_TRANSFER,RULE",
                "first": 5,
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        mock_client.get_activity.assert_called_once_with(
            org_id="org-1",
            first=5,
            after="",
            statuses=["COMPLETE", "PENDING"],
            directions=["INTERNAL"],
            activity_types=["ONE_TIME_TRANSFER", "RULE"],
        )

    def test_transfer_detail_by_org_path(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.get_transfer_detail.return_value = {
            "id": "tr-1",
            "status": "COMPLETE",
        }
        resp = client.get("/api/activity/org-1/tr-1", headers=_auth_headers())
        assert resp.status_code == 200
        assert resp.json()["id"] == "tr-1"
        mock_client.get_transfer_detail.assert_called_once_with("org-1", "tr-1")

    def test_transfer_status_uses_server_org_id(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.get_transfer_detail.return_value = {
            "id": "tr-1",
            "status": "COMPLETE",
        }
        resp = client.get("/api/transfers/tr-1", headers=_auth_headers())
        assert resp.status_code == 200
        assert resp.json()["id"] == "tr-1"
        mock_client.get_transfer_detail.assert_called_once_with("org-1", "tr-1")


class TestTransferSafeguards:
    def test_rejects_over_per_transfer_limit(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        app = _build_app(mock_client, tmp_path, max_transfer_cents=10000)
        tc = TestClient(app)
        resp = tc.post(
            "/api/transfers",
            json={
                "source_id": "p1",
                "destination_id": "p2",
                "amount_cents": 20000,
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 400
        assert "per-transfer limit" in resp.json()["detail"]

    def test_rejects_over_daily_limit(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        app = _build_app(mock_client, tmp_path, max_daily_transfer_cents=10000)
        tc = TestClient(app)

        # Record an existing transfer that uses most of the daily limit
        app.state.daily_limits.record(8000, "t-prev")

        resp = tc.post(
            "/api/transfers",
            json={
                "source_id": "p1",
                "destination_id": "p2",
                "amount_cents": 5000,
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 400
        assert "daily remaining limit" in resp.json()["detail"]

    def test_allows_valid_transfer(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        mock_client.transfer.return_value = {
            "id": "tr-new",
            "organization": {"id": "org-1"},
        }
        app = _build_app(mock_client, tmp_path)
        tc = TestClient(app)
        resp = tc.post(
            "/api/transfers",
            json={
                "source_id": "p1",
                "destination_id": "p2",
                "amount_cents": 5000,
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == "tr-new"
        mock_client.transfer.assert_called_once_with(
            kyc_id="kyc-1",
            source_id="p1",
            destination_id="p2",
            amount_cents=5000,
            source_type="POD",
            destination_type="POD",
            description="",
            instant=False,
        )

    def test_transfer_with_explicit_kyc_id(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        mock_client.transfer.return_value = {"id": "tr-new"}
        app = _build_app(mock_client, tmp_path)
        tc = TestClient(app)
        resp = tc.post(
            "/api/transfers",
            json={
                "kyc_id": "kyc-override",
                "source_id": "p1",
                "destination_id": "p2",
                "amount_cents": 5000,
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        mock_client.transfer.assert_called_once_with(
            kyc_id="kyc-override",
            source_id="p1",
            destination_id="p2",
            amount_cents=5000,
            source_type="POD",
            destination_type="POD",
            description="",
            instant=False,
        )

    def test_records_to_daily_limits_after_success(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        mock_client.transfer.return_value = {"id": "tr-new"}
        app = _build_app(mock_client, tmp_path, max_daily_transfer_cents=10000)
        tc = TestClient(app)

        tc.post(
            "/api/transfers",
            json={
                "source_id": "p1",
                "destination_id": "p2",
                "amount_cents": 6000,
            },
            headers=_auth_headers(),
        )

        _, remaining = app.state.daily_limits.check(0)
        assert remaining == 4000


class TestErrorHandling:
    def test_upstream_runtime_error_returns_502(
        self, client: TestClient, mock_client: MagicMock
    ) -> None:
        mock_client.get_pods.side_effect = RuntimeError(
            "HTTP 500: Internal Server Error"
        )
        resp = client.get("/api/pods", headers=_auth_headers())
        assert resp.status_code == 502
        assert "HTTP 500" in resp.json()["detail"]

    def test_transfer_business_error_returns_400(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        mock_client.transfer.side_effect = RuntimeError(
            "Transfer failed: Insufficient funds"
        )
        app = _build_app(mock_client, tmp_path)
        tc = TestClient(app)
        resp = tc.post(
            "/api/transfers",
            json={
                "source_id": "p1",
                "destination_id": "p2",
                "amount_cents": 100,
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 400
        assert "Insufficient funds" in resp.json()["detail"]

    def test_transfer_upstream_error_returns_502(
        self, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        mock_client.transfer.side_effect = RuntimeError("HTTP 500: Server error")
        app = _build_app(mock_client, tmp_path)
        tc = TestClient(app)
        resp = tc.post(
            "/api/transfers",
            json={
                "source_id": "p1",
                "destination_id": "p2",
                "amount_cents": 100,
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 502
