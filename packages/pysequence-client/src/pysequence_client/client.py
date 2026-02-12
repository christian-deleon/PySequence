"""HTTP client for the GetSequence API server."""

import logging
from typing import Any

import httpx
from pysequence_client.exceptions import ApiError


log = logging.getLogger(__name__)


class SequenceApiClient:
    """Client for the GetSequence REST API server."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"X-API-Key": api_key},
            timeout=timeout,
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        resp = self._client.request(method, path, **kwargs)

        if resp.status_code >= 400:
            content_type = resp.headers.get("content-type", "")

            if content_type.startswith("application/json"):
                detail = resp.json().get("detail", resp.text)
            else:
                detail = resp.text

            raise ApiError(resp.status_code, detail)
        
        return resp.json()

    # -- Pod operations --

    def get_pods(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/pods")

    def get_total_balance(self) -> dict[str, Any]:
        return self._request("GET", "/api/pods/balance")

    def get_pod_balance(self, pod_name: str) -> dict[str, Any] | None:
        try:
            return self._request("GET", f"/api/pods/{pod_name}/balance")
        
        except ApiError as e:
            if e.status_code == 404:
                return None
            
            raise

    def get_pod_detail(self, pod_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/pods/detail/{pod_id}")

    # -- Account operations --

    def get_all_accounts(self) -> dict[str, Any]:
        return self._request("GET", "/api/accounts")

    # -- Activity operations --

    def get_activity_summary(self) -> dict[str, Any]:
        return self._request("GET", "/api/activity/summary")

    def get_activity(
        self,
        first: int = 10,
        statuses: list[str] | None = None,
        directions: list[str] | None = None,
        activity_types: list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"first": first}

        if statuses:
            params["statuses"] = ",".join(statuses)

        if directions:
            params["directions"] = ",".join(directions)

        if activity_types:
            params["activity_types"] = ",".join(activity_types)
            
        return self._request("GET", "/api/activity", params=params)

    def get_transfer_detail(self, transfer_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/transfers/{transfer_id}")

    # -- Transfer operations --

    def transfer(
        self,
        source_id: str,
        destination_id: str,
        amount_cents: int,
        description: str = "",
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/transfers",
            json={
                "source_id": source_id,
                "destination_id": destination_id,
                "amount_cents": amount_cents,
                "description": description,
            },
        )

    def close(self) -> None:
        self._client.close()
