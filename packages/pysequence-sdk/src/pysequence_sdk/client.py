"""GetSequence GraphQL API client.

Uses curl_cffi with Chrome configuration for browser-compatible HTTP requests.
"""

import random
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from curl_cffi.requests import Session
from pysequence_sdk.graphql.mutations import CREATE_PAYMENT
from pysequence_sdk.graphql.queries import (
    ACTIVITY_LOG_TRANSFERS,
    ACTIVITY_SUMMARY,
    POD_DRAWER_CONTENT,
    SELECT_SOURCE_AND_DESTINATION,
    TRANSFER_REFERENCE_DETAIL,
)


GRAPHQL_ENDPOINT = "https://app.getsequence.io/api/graphql"
ORIGIN = "https://app.getsequence.io"
_ET = ZoneInfo("America/New_York")


def _to_eastern(utc_iso: str | None) -> str | None:
    """Convert a UTC ISO-8601 timestamp to Eastern time."""

    if not utc_iso:
        return utc_iso
    
    try:
        dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return utc_iso  # date-only string, no conversion needed
        return dt.astimezone(_ET).isoformat()
    
    except (ValueError, TypeError):
        return utc_iso


class SequenceClient:
    """GetSequence GraphQL API client.

    Uses curl_cffi with Chrome configuration for browser-compatible
    HTTP requests.
    """

    # Minimum seconds between any two requests
    _MIN_DELAY: float = 1.5

    # Maximum additional random jitter
    _MAX_JITTER: float = 2.0

    def __init__(
        self,
        access_token: str,
        token_provider: Callable[[], str] | None = None,
    ) -> None:
        self._token = access_token
        self._token_provider = token_provider

        self._session = Session(
            impersonate="chrome",
            timeout=30,
        )

        self._last_request_time: float = 0

    # -- low-level ---------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "accept": (
                "application/graphql-response+json, "
                "application/graphql+json, "
                "application/json, "
                "text/event-stream, "
                "multipart/mixed"
            ),
            "authorization": f"Bearer {self._token}",
            "content-type": "application/json",
            "origin": ORIGIN,
            "referer": f"{ORIGIN}/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-request-id": f"webapp-{uuid.uuid4()}",
        }

    def _wait(self) -> None:
        """Rate limiting between requests.

        Guarantees at least _MIN_DELAY + [0, _MAX_JITTER) seconds between
        any two requests.  If enough wall-clock time has already elapsed
        naturally the sleep is skipped.
        """

        if self._last_request_time == 0:
            return
        
        elapsed = time.monotonic() - self._last_request_time
        minimum = self._MIN_DELAY + random.uniform(0, self._MAX_JITTER)
        remaining = minimum - elapsed

        if remaining > 0:
            time.sleep(remaining)

    def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        operation_name: str | None = None,
    ) -> dict[str, Any]:
        if self._token_provider is not None:
            self._token = self._token_provider()

        payload: dict[str, Any] = {"query": query}

        if variables:
            payload["variables"] = variables

        if operation_name:
            payload["operationName"] = operation_name

        self._wait()

        resp = self._session.post(
            GRAPHQL_ENDPOINT,
            json=payload,
            headers=self._headers(),
        )

        self._last_request_time = time.monotonic()

        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        
        data = resp.json()

        if "errors" in data:
            raise RuntimeError(f"GraphQL errors: {data['errors']}")
        
        return data["data"]

    # -- high-level helpers ------------------------------------------------

    def get_pods(self) -> list[dict[str, Any]]:
        """Return every pod with its current balance."""

        data = self.execute(
            SELECT_SOURCE_AND_DESTINATION,
            operation_name="SelectSourceAndDestination",
        )

        memberships = data["me"]["memberships"]
        pods: list[dict[str, Any]] = []

        for m in memberships:
            org = m["organization"]
            for pod in org.get("pods", []):
                balance = pod.get("metadata", {}).get("balance", {})
                pods.append(
                    {
                        "id": pod["id"],
                        "name": pod["name"],
                        "organization_id": org["id"],
                        "balance_cents": balance.get("cents", 0),
                        "balance": balance.get("formatted", "$0.00"),
                    }
                )

        return pods

    def get_total_balance(self) -> dict[str, Any]:
        """Return the total balance across all pods."""

        pods = self.get_pods()
        total_cents = sum(pod["balance_cents"] for pod in pods)

        return {
            "total_balance_cents": total_cents,
            "total_balance": f"${total_cents / 100:,.2f}",
            "pod_count": len(pods),
        }

    def get_pod_balance(self, pod_name: str) -> dict[str, Any] | None:
        """Look up a single pod by name (case-insensitive) and return its balance info.

        Tries exact match first, then falls back to substring match
        if exactly one pod contains the search term.
        """

        pods = self.get_pods()
        name_lower = pod_name.lower()

        # Exact match
        for pod in pods:
            if pod["name"].lower() == name_lower:
                return pod

        # Substring fallback (only when exactly one pod matches)
        substring_matches = [p for p in pods if name_lower in p["name"].lower()]

        if len(substring_matches) == 1:
            return substring_matches[0]

        return None

    def get_pod_detail(self, organization_id: str, pod_id: str) -> dict[str, Any]:
        """Get detailed pod info including recent transfers."""

        data = self.execute(
            POD_DRAWER_CONTENT,
            variables={"organizationId": organization_id, "id": pod_id},
            operation_name="PodDrawerContent",
        )

        pod = data["organization"]["pod"]

        for edge in pod.get("transferReferences", {}).get("edges", []):
            node = edge.get("node", {})

            if "createdAt" in node:
                node["createdAt"] = _to_eastern(node["createdAt"])

        return pod

    def transfer(
        self,
        kyc_id: str,
        source_id: str,
        destination_id: str,
        amount_cents: int,
        source_type: str = "POD",
        destination_type: str = "POD",
        description: str = "",
        instant: bool = False,
    ) -> dict[str, Any]:
        """Transfer funds between pods/ports/accounts.

        Args:
            kyc_id: The KYC application ID (required by the API).
            source_id: UUID of the source pod/port/account.
            destination_id: UUID of the destination pod/port/account.
            amount_cents: Amount in cents (e.g. 100 = $1.00).
            source_type: One of "POD", "PORT", "ACCOUNT".
            destination_type: One of "POD", "PORT", "ACCOUNT".
            description: Optional ACH description.
            instant: Whether to use instant transfer.
        """
        variables = {
            "id": kyc_id,
            "source": {"id": source_id, "type": source_type},
            "destination": {"id": destination_id, "type": destination_type},
            "amount": amount_cents,
            "isInstantTransfer": instant,
            "achDescription": description,
        }

        data = self.execute(
            CREATE_PAYMENT,
            variables=variables,
            operation_name="CreatePayment",
        )

        result = data["forKYC"]["createPayment"]
        
        if result.get("error"):
            raise RuntimeError(f"Transfer failed: {result['error']['message']}")
        
        return result["ok"]

    def get_activity_summary(self) -> dict[str, Any]:
        """Return monthly activity summary: transfer count, rule executions, incoming funds."""

        data = self.execute(
            ACTIVITY_SUMMARY,
            operation_name="ActivitySummary",
        )

        summary = data["activitySummary"]
        incoming = summary.get("totalIncomingFundsInCents", {})

        return {
            "transfer_count": summary.get("transferReferencesCount", 0),
            "rule_executions": summary.get("ruleExecutionsCount", 0),
            "total_incoming_cents": incoming.get("cents", 0),
            "total_incoming": incoming.get("formatted", "$0.00"),
        }

    def get_activity(
        self,
        org_id: str,
        first: int = 10,
        after: str = "",
        date_start: str | None = None,
        date_end: str | None = None,
        statuses: list[str] | None = None,
        directions: list[str] | None = None,
        activity_types: list[str] | None = None,
        hide_internal: bool = False,
        name: str = "",
    ) -> dict[str, Any]:
        """Return paginated transfer activity with optional filters."""
        transfer_filter: dict[str, Any] = {}

        if date_start or date_end:
            created_at: dict[str, str] = {}

            if date_start:
                created_at["start"] = date_start

            if date_end:
                created_at["end"] = date_end

            transfer_filter["createdAt"] = created_at

        if statuses:
            transfer_filter["statuses"] = statuses

        if directions:
            transfer_filter["directions"] = directions

        if activity_types:
            transfer_filter["activityTypes"] = activity_types

        if hide_internal:
            transfer_filter["hideInternalTransfers"] = True

        if name:
            transfer_filter["name"] = name

        variables = {
            "organizationId": org_id,
            "transferFilter": transfer_filter,
            "first": first,
            "after": after,
        }

        data = self.execute(
            ACTIVITY_LOG_TRANSFERS,
            variables=variables,
            operation_name="ActivityLogV2Transfers",
        )

        org = data["organization"]
        refs = org["transferReferences"]
        edges = refs.get("edges", [])
        page_info = refs.get("pageInfo", {})

        transfers = []

        for edge in edges:
            node = edge["node"]
            transfers.append(
                {
                    "id": node["id"],
                    "type": node.get("type"),
                    "status": node.get("status"),
                    "error_reason": node.get("errorReason"),
                    "created_at": _to_eastern(node.get("createdAt")),
                    "updated_at": _to_eastern(node.get("updatedAt")),
                    "amount_cents": node.get("amount", {}).get("cents", 0),
                    "amount": node.get("amount", {}).get("formatted", "$0.00"),
                    "source": node.get("source", {}),
                    "destination": node.get("destination", {}),
                    "direction": node.get("direction"),
                    "activity_type": node.get("activityType"),
                }
            )

        return {
            "transfers": transfers,
            "page_info": {
                "end_cursor": page_info.get("endCursor", ""),
                "has_next_page": page_info.get("hasNextPage", False),
            },
        }

    def get_transfer_detail(
        self,
        org_id: str,
        transfer_id: str,
    ) -> dict[str, Any]:
        """Return full detail for a single transfer including status tracking."""
        data = self.execute(
            TRANSFER_REFERENCE_DETAIL,
            variables={"organizationId": org_id, "id": transfer_id},
            operation_name="TransferReferenceDrawerContentV2",
        )

        ref = data["organization"]["transferReference"]

        detail: dict[str, Any] = {
            "id": ref["id"],
            "type": ref.get("type"),
            "status": ref.get("status"),
            "error_reason": ref.get("errorReason"),
            "created_at": _to_eastern(ref.get("createdAt")),
            "updated_at": _to_eastern(ref.get("updatedAt")),
            "amount_cents": ref.get("amount", {}).get("cents", 0),
            "amount": ref.get("amount", {}).get("formatted", "$0.00"),
            "source": ref.get("source", {}),
            "destination": ref.get("destination", {}),
            "direction": ref.get("direction"),
            "activity_type": ref.get("activityType"),
        }

        # Parse transfer details (simple vs compound)
        details = ref.get("details")

        if details:
            typename = details.get("__typename", "")

            if typename == "SimpleTransferDetails":
                payment_status = details.get("status", {})

                detail["details"] = {
                    "type": "simple",
                    "status": payment_status.get("status"),
                    "created_at": _to_eastern(payment_status.get("createdAt")),
                    "completed_at": _to_eastern(payment_status.get("completedAt")),
                    "expected_completion": payment_status.get("expectedCompletionDate"),
                }

            elif typename == "CompoundTransferDetails":

                def _convert_ps(ps: dict | None) -> dict | None:
                    if not ps:
                        return ps
                    return {
                        **ps,
                        "createdAt": _to_eastern(ps.get("createdAt")),
                        "completedAt": _to_eastern(ps.get("completedAt")),
                    }

                detail["details"] = {
                    "type": "compound",
                    "pull": _convert_ps(details.get("pullPaymentStatus")),
                    "push": _convert_ps(details.get("pushPaymentStatus")),
                    "reversal": _convert_ps(details.get("reversalPaymentStatus")),
                }

        # Include rule details if present
        rule = ref.get("ruleDetails")
        if rule:
            detail["rule"] = {
                "trigger_type": rule.get("triggerType"),
                "trigger_cron": rule.get("triggerCron"),
            }

        return detail

    def get_all_accounts(self, org_id: str | None = None) -> dict[str, Any]:
        """Return all account types: pods, ports, and external accounts."""

        data = self.execute(
            SELECT_SOURCE_AND_DESTINATION,
            operation_name="SelectSourceAndDestination",
        )

        memberships = data["me"]["memberships"]

        pods: list[dict[str, Any]] = []
        ports: list[dict[str, Any]] = []
        accounts: list[dict[str, Any]] = []

        for m in memberships:
            org = m["organization"]

            if org_id and org["id"] != org_id:
                continue

            for pod in org.get("pods", []):
                balance = pod.get("metadata", {}).get("balance", {})

                pods.append(
                    {
                        "id": pod["id"],
                        "name": pod["name"],
                        "type": pod.get("type"),
                        "balance_cents": balance.get("cents", 0),
                        "balance": balance.get("formatted", "$0.00"),
                    }
                )

            for port in org.get("ports", []):
                balance = port.get("metadata", {}).get("balance", {})

                ports.append(
                    {
                        "id": port["id"],
                        "name": port["name"],
                        "balance_cents": balance.get("cents", 0),
                        "balance": balance.get("formatted", "$0.00"),
                    }
                )

            for account in org.get("accounts", []):
                meta = account.get("metadata", {})
                balance = meta.get("balance", {}) if meta else {}
                
                accounts.append(
                    {
                        "id": account["id"],
                        "name": account["name"],
                        "type": account.get("type"),
                        "provider_type": account.get("providerType"),
                        "institution": account.get("institutionName"),
                        "balance_cents": balance.get("cents", 0) if balance else 0,
                        "balance": (
                            balance.get("formatted", "$0.00") if balance else "$0.00"
                        ),
                    }
                )

        return {
            "pods": pods,
            "ports": ports,
            "accounts": accounts,
        }

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "SequenceClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
