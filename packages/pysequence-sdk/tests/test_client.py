"""Unit tests for pysequence_sdk.client."""

import time
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pysequence_sdk.client import (
    GRAPHQL_ENDPOINT,
    ORIGIN,
    SequenceClient,
    _to_eastern,
)


class FakeGqlResponse:
    def __init__(self, data: dict[str, Any], status_code: int = 200) -> None:
        self.status_code = status_code
        self._data = data
        self.text = str(data)

    def json(self) -> dict[str, Any]:
        return self._data


@pytest.fixture
def client() -> SequenceClient:
    c = SequenceClient("test-token-123")
    # Eliminate inter-request delays in tests
    c._last_request_time = 0
    return c


class TestHeaders:
    def test_authorization_header(self, client: SequenceClient) -> None:
        headers = client._headers()
        assert headers["authorization"] == "Bearer test-token-123"

    def test_origin_and_referer(self, client: SequenceClient) -> None:
        headers = client._headers()
        assert headers["origin"] == ORIGIN
        assert headers["referer"] == f"{ORIGIN}/"

    def test_sec_fetch_headers(self, client: SequenceClient) -> None:
        headers = client._headers()
        assert headers["sec-fetch-dest"] == "empty"
        assert headers["sec-fetch-mode"] == "cors"
        assert headers["sec-fetch-site"] == "same-origin"

    def test_request_id_format(self, client: SequenceClient) -> None:
        headers = client._headers()
        rid = headers["x-request-id"]
        assert rid.startswith("webapp-")
        # The part after "webapp-" should be a valid UUID
        uuid.UUID(rid.removeprefix("webapp-"))

    def test_accept_header_matches_webapp(self, client: SequenceClient) -> None:
        headers = client._headers()
        assert "application/graphql-response+json" in headers["accept"]


class TestExecute:
    def test_sends_query_and_returns_data(self, client: SequenceClient) -> None:
        fake_resp = FakeGqlResponse({"data": {"me": {"id": "1"}}})
        client._session = MagicMock()
        client._session.post.return_value = fake_resp

        result = client.execute("query { me { id } }", operation_name="Me")

        assert result == {"me": {"id": "1"}}
        call_kwargs = client._session.post.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["query"] == "query { me { id } }"
        assert payload["operationName"] == "Me"

    def test_sends_variables(self, client: SequenceClient) -> None:
        fake_resp = FakeGqlResponse({"data": {"pod": {}}})
        client._session = MagicMock()
        client._session.post.return_value = fake_resp

        client.execute(
            "query Q($id: ID!) { pod(id: $id) { id } }", variables={"id": "abc"}
        )

        payload = client._session.post.call_args.kwargs["json"]
        assert payload["variables"] == {"id": "abc"}

    def test_raises_on_http_error(self, client: SequenceClient) -> None:
        fake_resp = FakeGqlResponse({"error": "bad"}, status_code=401)
        fake_resp.text = "Unauthorized"
        client._session = MagicMock()
        client._session.post.return_value = fake_resp

        with pytest.raises(RuntimeError, match="HTTP 401"):
            client.execute("query { me { id } }")

    def test_raises_on_graphql_errors(self, client: SequenceClient) -> None:
        fake_resp = FakeGqlResponse(
            {"data": None, "errors": [{"message": "Field not found"}]}
        )
        client._session = MagicMock()
        client._session.post.return_value = fake_resp

        with pytest.raises(RuntimeError, match="GraphQL errors"):
            client.execute("query { bad }")


class TestGetPods:
    def test_parses_pods_from_response(self, client: SequenceClient) -> None:
        api_data = {
            "data": {
                "me": {
                    "memberships": [
                        {
                            "organization": {
                                "id": "org-1",
                                "pods": [
                                    {
                                        "id": "pod-1",
                                        "name": "Groceries",
                                        "metadata": {
                                            "balance": {
                                                "cents": 5000,
                                                "formatted": "$50.00",
                                            }
                                        },
                                    },
                                    {
                                        "id": "pod-2",
                                        "name": "Rent",
                                        "metadata": {
                                            "balance": {
                                                "cents": 120000,
                                                "formatted": "$1,200.00",
                                            }
                                        },
                                    },
                                ],
                            }
                        }
                    ]
                }
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        pods = client.get_pods()

        assert len(pods) == 2
        groceries = next(p for p in pods if p["name"] == "Groceries")
        assert groceries["balance_cents"] == 5000
        assert groceries["balance"] == "$50.00"
        assert groceries["organization_id"] == "org-1"

    def test_handles_empty_pods(self, client: SequenceClient) -> None:
        api_data = {
            "data": {
                "me": {"memberships": [{"organization": {"id": "org-1", "pods": []}}]}
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        assert client.get_pods() == []


class TestGetTotalBalance:
    def test_sums_all_pod_balances(self, client: SequenceClient) -> None:
        api_data = {
            "data": {
                "me": {
                    "memberships": [
                        {
                            "organization": {
                                "id": "org-1",
                                "pods": [
                                    {
                                        "id": "pod-1",
                                        "name": "Groceries",
                                        "metadata": {
                                            "balance": {
                                                "cents": 5000,
                                                "formatted": "$50.00",
                                            }
                                        },
                                    },
                                    {
                                        "id": "pod-2",
                                        "name": "Rent",
                                        "metadata": {
                                            "balance": {
                                                "cents": 120000,
                                                "formatted": "$1,200.00",
                                            }
                                        },
                                    },
                                ],
                            }
                        }
                    ]
                }
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        result = client.get_total_balance()

        assert result["total_balance_cents"] == 125000
        assert result["total_balance"] == "$1,250.00"
        assert result["pod_count"] == 2

    def test_returns_zero_when_no_pods(self, client: SequenceClient) -> None:
        api_data = {
            "data": {
                "me": {"memberships": [{"organization": {"id": "org-1", "pods": []}}]}
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        result = client.get_total_balance()

        assert result["total_balance_cents"] == 0
        assert result["total_balance"] == "$0.00"
        assert result["pod_count"] == 0


class TestGetPodBalance:
    def test_finds_pod_case_insensitive(self, client: SequenceClient) -> None:
        api_data = {
            "data": {
                "me": {
                    "memberships": [
                        {
                            "organization": {
                                "id": "org-1",
                                "pods": [
                                    {
                                        "id": "pod-1",
                                        "name": "Groceries",
                                        "metadata": {
                                            "balance": {
                                                "cents": 5000,
                                                "formatted": "$50.00",
                                            }
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        result = client.get_pod_balance("groceries")
        assert result is not None
        assert result["name"] == "Groceries"

    def test_substring_match_single(self, client: SequenceClient) -> None:
        api_data = {
            "data": {
                "me": {
                    "memberships": [
                        {
                            "organization": {
                                "id": "org-1",
                                "pods": [
                                    {
                                        "id": "pod-1",
                                        "name": "Christian's Groceries",
                                        "metadata": {
                                            "balance": {
                                                "cents": 5000,
                                                "formatted": "$50.00",
                                            }
                                        },
                                    },
                                    {
                                        "id": "pod-2",
                                        "name": "Rent",
                                        "metadata": {
                                            "balance": {
                                                "cents": 120000,
                                                "formatted": "$1,200.00",
                                            }
                                        },
                                    },
                                ],
                            }
                        }
                    ]
                }
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        result = client.get_pod_balance("groceries")
        assert result is not None
        assert result["name"] == "Christian's Groceries"

    def test_substring_match_ambiguous_returns_none(
        self, client: SequenceClient
    ) -> None:
        api_data = {
            "data": {
                "me": {
                    "memberships": [
                        {
                            "organization": {
                                "id": "org-1",
                                "pods": [
                                    {
                                        "id": "pod-1",
                                        "name": "Christian's Savings",
                                        "metadata": {
                                            "balance": {
                                                "cents": 5000,
                                                "formatted": "$50.00",
                                            }
                                        },
                                    },
                                    {
                                        "id": "pod-2",
                                        "name": "Carly's Savings",
                                        "metadata": {
                                            "balance": {
                                                "cents": 3000,
                                                "formatted": "$30.00",
                                            }
                                        },
                                    },
                                ],
                            }
                        }
                    ]
                }
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        assert client.get_pod_balance("savings") is None

    def test_exact_match_takes_priority(self, client: SequenceClient) -> None:
        api_data = {
            "data": {
                "me": {
                    "memberships": [
                        {
                            "organization": {
                                "id": "org-1",
                                "pods": [
                                    {
                                        "id": "pod-1",
                                        "name": "Groceries",
                                        "metadata": {
                                            "balance": {
                                                "cents": 5000,
                                                "formatted": "$50.00",
                                            }
                                        },
                                    },
                                    {
                                        "id": "pod-2",
                                        "name": "Christian's Groceries",
                                        "metadata": {
                                            "balance": {
                                                "cents": 3000,
                                                "formatted": "$30.00",
                                            }
                                        },
                                    },
                                ],
                            }
                        }
                    ]
                }
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        result = client.get_pod_balance("Groceries")
        assert result is not None
        assert result["name"] == "Groceries"
        assert result["id"] == "pod-1"

    def test_returns_none_for_missing_pod(self, client: SequenceClient) -> None:
        api_data = {
            "data": {
                "me": {"memberships": [{"organization": {"id": "org-1", "pods": []}}]}
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        assert client.get_pod_balance("Nonexistent") is None


class TestTransfer:
    def test_returns_ok_payload(self, client: SequenceClient) -> None:
        api_data = {
            "data": {
                "forKYC": {
                    "createPayment": {
                        "ok": {"organization": {"id": "org-1", "pods": []}},
                        "error": None,
                    }
                }
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        result = client.transfer(
            kyc_id="kyc-1",
            source_id="pod-1",
            destination_id="pod-2",
            amount_cents=100,
        )
        assert result == {"organization": {"id": "org-1", "pods": []}}

    def test_raises_on_transfer_error(self, client: SequenceClient) -> None:
        api_data = {
            "data": {
                "forKYC": {
                    "createPayment": {
                        "ok": None,
                        "error": {"message": "Insufficient funds"},
                    }
                }
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        with pytest.raises(RuntimeError, match="Insufficient funds"):
            client.transfer("kyc-1", "pod-1", "pod-2", 100)


class TestGetActivitySummary:
    def test_parses_summary(self, client: SequenceClient) -> None:
        api_data = {
            "data": {
                "me": {
                    "id": "u1",
                    "offer": None,
                    "settings": {"id": "s1", "showSinceYouveBeenGone": True},
                },
                "activitySummary": {
                    "id": "as-1",
                    "transferReferencesCount": 42,
                    "ruleExecutionsCount": 7,
                    "totalIncomingFundsInCents": {
                        "cents": 150000,
                        "formatted": "$1,500.00",
                    },
                },
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        result = client.get_activity_summary()

        assert result["transfer_count"] == 42
        assert result["rule_executions"] == 7
        assert result["total_incoming_cents"] == 150000
        assert result["total_incoming"] == "$1,500.00"


class TestGetActivity:
    def test_parses_transfers_and_pagination(self, client: SequenceClient) -> None:
        api_data = {
            "data": {
                "me": {"id": "u1", "offer": None},
                "organization": {
                    "id": "org-1",
                    "firstTransferDate": "2024-01-01",
                    "kycs": [],
                    "plan": {
                        "id": "p1",
                        "name": "Free",
                        "transactionsPerMonth": 50,
                        "transferExtraCharge": {"formatted": "$0.00"},
                    },
                    "subscriptionPayment": None,
                    "transferReferences": {
                        "pageInfo": {
                            "endCursor": "cursor-abc",
                            "hasNextPage": True,
                        },
                        "edges": [
                            {
                                "cursor": "c1",
                                "node": {
                                    "id": "tr-1",
                                    "type": "TRANSFER",
                                    "status": "COMPLETE",
                                    "errorReason": None,
                                    "createdAt": "2025-02-01T10:00:00Z",
                                    "updatedAt": "2025-02-01T10:01:00Z",
                                    "amount": {"cents": 5000, "formatted": "$50.00"},
                                    "source": {
                                        "id": "pod-1",
                                        "name": "Savings",
                                        "icon": "piggy",
                                        "__typename": "Pod",
                                    },
                                    "destination": {
                                        "id": "pod-2",
                                        "name": "Groceries",
                                        "icon": "cart",
                                        "__typename": "Pod",
                                    },
                                    "direction": "INTERNAL",
                                    "activityType": "ONE_TIME_TRANSFER",
                                    "description": "Weekly groceries",
                                    "ruleDetails": None,
                                },
                            },
                        ],
                    },
                },
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        result = client.get_activity(org_id="org-1", first=10)

        assert len(result["transfers"]) == 1
        t = result["transfers"][0]
        assert t["id"] == "tr-1"
        assert t["status"] == "COMPLETE"
        assert t["amount_cents"] == 5000
        assert t["direction"] == "INTERNAL"
        assert t["activity_type"] == "ONE_TIME_TRANSFER"
        assert result["page_info"]["has_next_page"] is True
        assert result["page_info"]["end_cursor"] == "cursor-abc"

    def test_passes_filters_in_variables(self, client: SequenceClient) -> None:
        api_data = {
            "data": {
                "me": {"id": "u1", "offer": None},
                "organization": {
                    "id": "org-1",
                    "firstTransferDate": None,
                    "kycs": [],
                    "plan": None,
                    "subscriptionPayment": None,
                    "transferReferences": {
                        "pageInfo": {"endCursor": "", "hasNextPage": False},
                        "edges": [],
                    },
                },
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        client.get_activity(
            org_id="org-1",
            first=5,
            statuses=["PENDING"],
            directions=["OUTGOING"],
            activity_types=["RULE"],
            hide_internal=True,
            name="rent",
        )

        payload = client._session.post.call_args.kwargs["json"]
        tf = payload["variables"]["transferFilter"]
        assert tf["statuses"] == ["PENDING"]
        assert tf["directions"] == ["OUTGOING"]
        assert tf["activityTypes"] == ["RULE"]
        assert tf["hideInternalTransfers"] is True
        assert tf["name"] == "rent"


class TestGetTransferDetail:
    def test_parses_simple_details(self, client: SequenceClient) -> None:
        api_data = {
            "data": {
                "organization": {
                    "id": "org-1",
                    "transferReference": {
                        "id": "tr-1",
                        "type": "TRANSFER",
                        "status": "COMPLETE",
                        "errorReason": None,
                        "createdAt": "2025-02-01T10:00:00Z",
                        "updatedAt": "2025-02-01T10:01:00Z",
                        "amount": {"cents": 5000, "formatted": "$50.00"},
                        "source": {
                            "id": "pod-1",
                            "name": "Savings",
                            "__typename": "Pod",
                        },
                        "destination": {
                            "id": "pod-2",
                            "name": "Groceries",
                            "__typename": "Pod",
                        },
                        "direction": "INTERNAL",
                        "activityType": "ONE_TIME_TRANSFER",
                        "description": "Weekly groceries",
                        "details": {
                            "__typename": "SimpleTransferDetails",
                            "status": {
                                "status": "COMPLETE",
                                "createdAt": "2025-02-01T10:00:00Z",
                                "completedAt": "2025-02-01T10:01:00Z",
                                "expectedCompletionDate": None,
                                "__typename": "PaymentStatus",
                            },
                        },
                        "ruleDetails": None,
                    },
                }
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        result = client.get_transfer_detail("org-1", "tr-1")

        assert result["id"] == "tr-1"
        assert result["status"] == "COMPLETE"
        assert result["details"]["type"] == "simple"
        assert result["details"]["completed_at"] == "2025-02-01T05:01:00-05:00"
        assert "rule" not in result

    def test_parses_compound_details(self, client: SequenceClient) -> None:
        api_data = {
            "data": {
                "organization": {
                    "id": "org-1",
                    "transferReference": {
                        "id": "tr-2",
                        "type": "TRANSFER",
                        "status": "PENDING",
                        "errorReason": None,
                        "createdAt": "2025-02-01T10:00:00Z",
                        "updatedAt": "2025-02-01T10:00:00Z",
                        "amount": {"cents": 10000, "formatted": "$100.00"},
                        "source": {
                            "id": "acc-1",
                            "name": "Chase",
                            "__typename": "Account",
                        },
                        "destination": {
                            "id": "pod-1",
                            "name": "Savings",
                            "__typename": "Pod",
                        },
                        "direction": "INCOMING",
                        "activityType": "PULLED_FROM_SEQUENCE",
                        "description": None,
                        "details": {
                            "__typename": "CompoundTransferDetails",
                            "pullPaymentStatus": {
                                "status": "COMPLETE",
                                "createdAt": "2025-02-01T10:00:00Z",
                                "completedAt": "2025-02-01T10:01:00Z",
                                "expectedCompletionDate": None,
                            },
                            "pushPaymentStatus": {
                                "status": "PENDING",
                                "createdAt": "2025-02-01T10:01:00Z",
                                "completedAt": None,
                                "expectedCompletionDate": "2025-02-03",
                            },
                            "reversalPaymentStatus": None,
                        },
                        "ruleDetails": None,
                    },
                }
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        result = client.get_transfer_detail("org-1", "tr-2")

        assert result["details"]["type"] == "compound"
        assert result["details"]["pull"]["status"] == "COMPLETE"
        assert result["details"]["push"]["status"] == "PENDING"

    def test_parses_rule_details(self, client: SequenceClient) -> None:
        api_data = {
            "data": {
                "organization": {
                    "id": "org-1",
                    "transferReference": {
                        "id": "tr-3",
                        "type": "TRANSFER",
                        "status": "COMPLETE",
                        "errorReason": None,
                        "createdAt": "2025-02-01T10:00:00Z",
                        "updatedAt": "2025-02-01T10:01:00Z",
                        "amount": {"cents": 2500, "formatted": "$25.00"},
                        "source": {
                            "id": "port-1",
                            "name": "Payroll",
                            "__typename": "Port",
                        },
                        "destination": {
                            "id": "pod-1",
                            "name": "Groceries",
                            "__typename": "Pod",
                        },
                        "direction": "INTERNAL",
                        "activityType": "RULE",
                        "description": "Auto-split",
                        "details": None,
                        "ruleDetails": {
                            "triggerType": "ON_MONEY_IN",
                            "triggerCron": None,
                            "__typename": "RuleDetails",
                        },
                    },
                }
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        result = client.get_transfer_detail("org-1", "tr-3")

        assert result["rule"]["trigger_type"] == "ON_MONEY_IN"
        assert result["rule"]["trigger_cron"] is None


class TestGetAllAccounts:
    def test_returns_categorized_accounts(self, client: SequenceClient) -> None:
        api_data = {
            "data": {
                "me": {
                    "memberships": [
                        {
                            "organization": {
                                "id": "org-1",
                                "pods": [
                                    {
                                        "id": "pod-1",
                                        "name": "Groceries",
                                        "type": "REGULAR",
                                        "metadata": {
                                            "balance": {
                                                "cents": 5000,
                                                "formatted": "$50.00",
                                            }
                                        },
                                    },
                                ],
                                "ports": [
                                    {
                                        "id": "port-1",
                                        "name": "Payroll",
                                        "metadata": {
                                            "balance": {
                                                "cents": 300000,
                                                "formatted": "$3,000.00",
                                            }
                                        },
                                    },
                                ],
                                "accounts": [
                                    {
                                        "id": "acc-1",
                                        "name": "Chase Checking",
                                        "type": "CHECKING",
                                        "providerType": "PLAID",
                                        "institutionName": "Chase",
                                        "metadata": {
                                            "__typename": "PlaidMetadata",
                                            "id": "pm-1",
                                            "balance": {
                                                "cents": 250000,
                                                "formatted": "$2,500.00",
                                            },
                                            "institution": {
                                                "id": "ins-1",
                                                "name": "Chase",
                                                "logo": None,
                                            },
                                        },
                                    },
                                ],
                            }
                        }
                    ]
                }
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        result = client.get_all_accounts(org_id="org-1")

        assert len(result["pods"]) == 1
        assert result["pods"][0]["name"] == "Groceries"
        assert result["pods"][0]["balance_cents"] == 5000
        assert len(result["ports"]) == 1
        assert result["ports"][0]["name"] == "Payroll"
        assert result["ports"][0]["balance_cents"] == 300000
        assert len(result["accounts"]) == 1
        assert result["accounts"][0]["name"] == "Chase Checking"
        assert result["accounts"][0]["institution"] == "Chase"

    def test_filters_by_org_id(self, client: SequenceClient) -> None:
        api_data = {
            "data": {
                "me": {
                    "memberships": [
                        {
                            "organization": {
                                "id": "org-1",
                                "pods": [
                                    {
                                        "id": "p1",
                                        "name": "A",
                                        "metadata": {
                                            "balance": {
                                                "cents": 100,
                                                "formatted": "$1.00",
                                            }
                                        },
                                    }
                                ],
                                "ports": [],
                                "accounts": [],
                            }
                        },
                        {
                            "organization": {
                                "id": "org-2",
                                "pods": [
                                    {
                                        "id": "p2",
                                        "name": "B",
                                        "metadata": {
                                            "balance": {
                                                "cents": 200,
                                                "formatted": "$2.00",
                                            }
                                        },
                                    }
                                ],
                                "ports": [],
                                "accounts": [],
                            }
                        },
                    ]
                }
            }
        }
        client._session = MagicMock()
        client._session.post.return_value = FakeGqlResponse(api_data)

        result = client.get_all_accounts(org_id="org-1")

        assert len(result["pods"]) == 1
        assert result["pods"][0]["name"] == "A"


class TestWait:
    def test_no_sleep_on_first_request(self) -> None:
        c = SequenceClient("tok")
        with patch("pysequence_sdk.client.time.sleep") as mock_sleep:
            c._wait()
            mock_sleep.assert_not_called()

    def test_sleeps_at_least_min_delay_on_back_to_back(self) -> None:
        c = SequenceClient("tok")
        c._MIN_DELAY = 0.2
        c._MAX_JITTER = 0.0
        c._last_request_time = time.monotonic()

        start = time.monotonic()
        c._wait()
        elapsed = time.monotonic() - start

        assert elapsed >= 0.2

    def test_no_sleep_when_enough_time_elapsed(self) -> None:
        c = SequenceClient("tok")
        c._MIN_DELAY = 0.05
        c._MAX_JITTER = 0.0
        # Pretend last request was long ago
        c._last_request_time = time.monotonic() - 10.0

        with patch("pysequence_sdk.client.time.sleep") as mock_sleep:
            c._wait()
            mock_sleep.assert_not_called()


class TestToEastern:
    def test_converts_utc_to_eastern(self) -> None:
        # Feb is EST (UTC-5)
        assert _to_eastern("2025-02-01T10:00:00Z") == "2025-02-01T05:00:00-05:00"

    def test_converts_utc_summer_to_edt(self) -> None:
        # Jul is EDT (UTC-4)
        assert _to_eastern("2025-07-01T10:00:00Z") == "2025-07-01T06:00:00-04:00"

    def test_returns_none_for_none(self) -> None:
        assert _to_eastern(None) is None

    def test_returns_empty_for_empty(self) -> None:
        assert _to_eastern("") == ""

    def test_preserves_date_only_strings(self) -> None:
        assert _to_eastern("2025-02-03") == "2025-02-03"


class TestTokenProvider:
    def test_refreshes_token_before_execute(self) -> None:
        c = SequenceClient("old-token", token_provider=lambda: "new-token")
        c._last_request_time = 0
        fake_resp = FakeGqlResponse({"data": {"me": {"id": "1"}}})
        c._session = MagicMock()
        c._session.post.return_value = fake_resp

        c.execute("query { me { id } }")

        headers = c._session.post.call_args.kwargs["headers"]
        assert headers["authorization"] == "Bearer new-token"
        assert c._token == "new-token"

    def test_no_refresh_when_provider_is_none(self) -> None:
        c = SequenceClient("static-token")
        c._last_request_time = 0
        fake_resp = FakeGqlResponse({"data": {"me": {"id": "1"}}})
        c._session = MagicMock()
        c._session.post.return_value = fake_resp

        c.execute("query { me { id } }")

        headers = c._session.post.call_args.kwargs["headers"]
        assert headers["authorization"] == "Bearer static-token"


class TestContextManager:
    def test_close_called_on_exit(self) -> None:
        client = SequenceClient("tok")
        client._session = MagicMock()
        with client:
            pass
        client._session.close.assert_called_once()
