"""Tool definitions and execution for the AI agent.

Defines the tools Claude can call and validates/executes them
against the Sequence SDK.
"""

import json
import logging
import time
import uuid
from typing import Any

from pysequence_sdk import SequenceClient
from pysequence_sdk.safeguards import AuditLog, DailyLimitTracker

from pysequence_bot.ai.memory import MemoryStore
from pysequence_bot.config import AgentConfig, SdkConfig

log = logging.getLogger(__name__)

TOOLS = [
    {
        "name": "get_all_pods",
        "description": (
            "List all pods with their current balances. "
            "Use this when the user asks about all pods "
            "or needs to compare/rank pods."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_total_balance",
        "description": (
            "Get the total balance across all pods. "
            "Use this when the user asks about their total balance or overall account value."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_pod_balance",
        "description": (
            "Look up a single pod by name and return its balance. "
            "Use this when the user asks about a specific pod's balance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pod_name": {
                    "type": "string",
                    "description": "The name of the pod to look up (case-insensitive).",
                },
            },
            "required": ["pod_name"],
        },
    },
    {
        "name": "get_pod_detail",
        "description": (
            "Get detailed info about a pod including bank details and recent transfers. "
            "Use this when the user asks for details beyond just the balance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pod_id": {
                    "type": "string",
                    "description": "The pod's unique ID.",
                },
            },
            "required": ["pod_id"],
        },
    },
    {
        "name": "request_transfer",
        "description": (
            "Stage a transfer between two pods or ports. This does NOT execute the transfer — "
            "it validates the request and returns a confirmation payload. "
            "The user must explicitly confirm before the transfer executes. "
            "You MUST always include a note. Infer a short, clear description from "
            "context (e.g. 'Weekly groceries', 'Rent payment'). If the context is too "
            "vague to infer a meaningful description, ask the user before calling this "
            "tool. Only omit the note if the user explicitly says not to bother."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_name": {
                    "type": "string",
                    "description": "Name of the source pod or port (case-insensitive).",
                },
                "destination_name": {
                    "type": "string",
                    "description": "Name of the destination pod or port (case-insensitive).",
                },
                "amount_dollars": {
                    "type": "number",
                    "description": "Amount to transfer in dollars (e.g. 50.00).",
                },
                "note": {
                    "type": "string",
                    "description": (
                        "Short description for the transfer (max 100 characters). "
                        "Always provide this unless the user explicitly opts out."
                    ),
                },
            },
            "required": ["source_name", "destination_name", "amount_dollars"],
        },
    },
    {
        "name": "cancel_transfer",
        "description": (
            "Cancel a previously staged transfer. "
            "Use when the user says 'cancel', 'never mind', or wants to abandon "
            "a pending transfer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pending_transfer_id": {
                    "type": "string",
                    "description": "The ID of the pending transfer to cancel.",
                },
            },
            "required": ["pending_transfer_id"],
        },
    },
    {
        "name": "get_recent_activity",
        "description": (
            "Get recent transfer activity. "
            "Use when user asks about recent transactions, what happened today, "
            "transfer history, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Number of transfers to return (default 10).",
                },
                "direction": {
                    "type": "string",
                    "enum": ["INTERNAL", "OUTGOING", "INCOMING"],
                    "description": "Filter by transfer direction.",
                },
                "status": {
                    "type": "string",
                    "enum": ["COMPLETE", "PENDING"],
                    "description": "Filter by transfer status.",
                },
                "activity_type": {
                    "type": "string",
                    "enum": [
                        "ONE_TIME_TRANSFER",
                        "RULE",
                        "PULLED_FROM_SEQUENCE",
                        "MONEY_IN",
                        "CASHBACK",
                    ],
                    "description": "Filter by activity type.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_transfer_status",
        "description": (
            "Get detailed status of a specific transfer. "
            "Use when user asks about a transfer's status, expected completion, or details."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "transfer_id": {
                    "type": "string",
                    "description": "The transfer reference ID.",
                },
            },
            "required": ["transfer_id"],
        },
    },
    {
        "name": "get_activity_summary",
        "description": (
            "Get a summary of recent activity including transfer count, "
            "rule executions, and incoming funds."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_all_accounts",
        "description": (
            "List all accounts including pods, ports (income sources), and external accounts "
            "(bank accounts, credit cards). Use when the user asks about all their accounts, "
            "ports, external accounts, or account types beyond just pods."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "save_memory",
        "description": (
            "Save a fact to persistent memory. Use this to remember user preferences, "
            "pod nicknames, spending patterns, or any useful context. "
            "Pass an existing fact_id to update a fact instead of creating a new one."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The fact to remember.",
                },
                "fact_id": {
                    "type": "string",
                    "description": "Optional ID of an existing fact to update in place.",
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "delete_memory",
        "description": "Delete a fact from persistent memory by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fact_id": {
                    "type": "string",
                    "description": "The ID of the fact to delete.",
                },
            },
            "required": ["fact_id"],
        },
    },
    {
        "name": "list_memories",
        "description": (
            "List all facts currently stored in persistent memory. "
            "Use this when the user asks what you remember."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


def _find_pod(name: str, pods: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find a pod by exact match, then single-substring match."""
    name_lower = name.lower()
    for pod in pods:
        if pod["name"].lower() == name_lower:
            return pod
    substring_matches = [p for p in pods if name_lower in p["name"].lower()]
    if len(substring_matches) == 1:
        return substring_matches[0]
    return None


def _suggest_pods(name: str, pods: list[dict[str, Any]]) -> str:
    """Return a suggestion suffix for unmatched pod names."""
    name_lower = name.lower()
    substring_matches = [p for p in pods if name_lower in p["name"].lower()]
    if substring_matches:
        names = ", ".join(p["name"] for p in substring_matches)
        return f" Did you mean: {names}?"
    return " Try using get_all_pods to see available pods."


def _find_port(name: str, ports: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find a port by exact match, then single-substring match."""
    name_lower = name.lower()
    for port in ports:
        if port["name"].lower() == name_lower:
            return port
    substring_matches = [p for p in ports if name_lower in p["name"].lower()]
    if len(substring_matches) == 1:
        return substring_matches[0]
    return None


def _suggest_ports(name: str, ports: list[dict[str, Any]]) -> str:
    """Return a suggestion suffix for unmatched port names."""
    name_lower = name.lower()
    substring_matches = [p for p in ports if name_lower in p["name"].lower()]
    if substring_matches:
        names = ", ".join(p["name"] for p in substring_matches)
        return f" Did you mean: {names}?"
    return " Try using get_all_accounts to see available ports."


def _find_account_by_name(
    name: str, pods: list[dict[str, Any]], ports: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Search across pods and ports by name.

    Return dict with id, name, type, balance_cents, balance.
    Exact match first, then single-substring. Returns None if ambiguous or not found.
    """
    name_lower = name.lower()

    # Exact match across both
    for pod in pods:
        if pod["name"].lower() == name_lower:
            return {
                "id": pod["id"],
                "name": pod["name"],
                "type": "POD",
                "balance_cents": pod["balance_cents"],
                "balance": pod["balance"],
            }
    for port in ports:
        if port["name"].lower() == name_lower:
            return {
                "id": port["id"],
                "name": port["name"],
                "type": "PORT",
                "balance_cents": port["balance_cents"],
                "balance": port["balance"],
            }

    # Substring match across both
    all_items = [(p, "POD") for p in pods] + [(p, "PORT") for p in ports]
    substring_matches = [
        (item, typ) for item, typ in all_items if name_lower in item["name"].lower()
    ]
    if len(substring_matches) == 1:
        item, typ = substring_matches[0]
        return {
            "id": item["id"],
            "name": item["name"],
            "type": typ,
            "balance_cents": item["balance_cents"],
            "balance": item["balance"],
        }
    return None


def execute_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    client: SequenceClient,
    agent_config: AgentConfig,
    pending_transfers: dict[str, dict],
    sdk_config: SdkConfig | None = None,
    memory: MemoryStore | None = None,
    user_name: str | None = None,
    user_id: int | None = None,
    staged_this_turn: list[str] | None = None,
    daily_limits: DailyLimitTracker | None = None,
    audit: AuditLog | None = None,
) -> str:
    """Execute a tool call and return the result as a JSON string."""
    log.info("Executing tool: %s with input: %s", tool_name, tool_input)

    org_id = sdk_config.org_id if sdk_config else None

    if tool_name == "get_all_pods":
        pods = client.get_pods()
        result = {"pods": pods, "count": len(pods)}
        log.info("get_all_pods returned %d pods", len(pods))
        return json.dumps(result)

    if tool_name == "get_total_balance":
        result = client.get_total_balance()
        log.info("get_total_balance -> %s", result["total_balance"])
        return json.dumps(result)

    if tool_name == "get_pod_balance":
        pod_name = tool_input["pod_name"]
        pods = client.get_pods()
        pod = _find_pod(pod_name, pods)
        if pod is None:
            suggestion = _suggest_pods(pod_name, pods)
            result = {"error": f"Pod '{pod_name}' not found.{suggestion}"}
        else:
            result = pod
        log.info("get_pod_balance(%s) -> %s", pod_name, "found" if pod else "not found")
        return json.dumps(result)

    if tool_name == "get_pod_detail":
        pod_id = tool_input["pod_id"]
        detail = client.get_pod_detail(org_id, pod_id)
        log.info("get_pod_detail(%s) -> success", pod_id)
        return json.dumps(detail)

    if tool_name == "request_transfer":
        return _handle_request_transfer(
            tool_input,
            client,
            agent_config,
            pending_transfers,
            sdk_config=sdk_config,
            user_id=user_id,
            staged_this_turn=staged_this_turn,
            daily_limits=daily_limits,
            audit=audit,
            user_name=user_name,
        )

    if tool_name == "cancel_transfer":
        return _handle_cancel_transfer(
            tool_input, pending_transfers, user_id=user_id, audit=audit
        )

    if tool_name == "get_recent_activity":
        return _handle_get_recent_activity(tool_input, client, org_id)

    if tool_name == "get_transfer_status":
        return _handle_get_transfer_status(tool_input, client, org_id)

    if tool_name == "get_activity_summary":
        return _handle_get_activity_summary(client)

    if tool_name == "get_all_accounts":
        return _handle_get_all_accounts(client, org_id)

    if tool_name == "save_memory":
        return _handle_save_memory(tool_input, memory, user_name)

    if tool_name == "delete_memory":
        return _handle_delete_memory(tool_input, memory)

    if tool_name == "list_memories":
        return _handle_list_memories(memory)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


def _handle_request_transfer(
    tool_input: dict[str, Any],
    client: SequenceClient,
    agent_config: AgentConfig,
    pending_transfers: dict[str, dict],
    *,
    sdk_config: SdkConfig | None = None,
    user_id: int | None = None,
    staged_this_turn: list[str] | None = None,
    daily_limits: DailyLimitTracker | None = None,
    audit: AuditLog | None = None,
    user_name: str | None = None,
) -> str:
    """Validate and stage a transfer request."""
    source_name = tool_input["source_name"]
    destination_name = tool_input["destination_name"]
    amount_dollars = tool_input["amount_dollars"]
    note = tool_input.get("note", "")

    # Validate note length
    if len(note) > 100:
        return json.dumps(
            {
                "error": f"Note is too long ({len(note)} chars). Maximum is 100 characters."
            }
        )

    # Validate amount
    if not isinstance(amount_dollars, (int, float)) or amount_dollars <= 0:
        return json.dumps({"error": "Amount must be a positive number."})

    amount_cents = round(amount_dollars * 100)

    if amount_cents > agent_config.max_transfer_amount_cents:
        max_dollars = agent_config.max_transfer_amount_cents / 100
        return json.dumps(
            {
                "error": f"Amount ${amount_dollars:.2f} exceeds the maximum transfer limit of ${max_dollars:,.2f}."
            }
        )

    # Check daily cumulative limit
    if daily_limits is not None and user_id is not None:
        allowed, remaining = daily_limits.check(amount_cents, user_id=user_id)
        if not allowed:
            max_daily = agent_config.max_daily_transfer_cents / 100
            used = max_daily - remaining / 100
            return json.dumps(
                {
                    "error": (
                        f"This transfer would exceed your daily limit of "
                        f"${max_daily:,.2f}. You've transferred ${used:,.2f} today. "
                        f"Remaining: ${remaining / 100:,.2f}."
                    )
                }
            )

    # Resolve source and destination across pods and ports
    org_id = sdk_config.org_id if sdk_config else None
    all_accounts = client.get_all_accounts(org_id)
    pods = all_accounts["pods"]
    ports = all_accounts["ports"]

    source = _find_account_by_name(source_name, pods, ports)
    if source is None:
        suggestion = _suggest_pods(source_name, pods)
        return json.dumps({"error": f"Source '{source_name}' not found.{suggestion}"})

    destination = _find_account_by_name(destination_name, pods, ports)
    if destination is None:
        suggestion = _suggest_pods(destination_name, pods)
        return json.dumps(
            {"error": f"Destination '{destination_name}' not found.{suggestion}"}
        )

    # Check sufficient balance
    if source["balance_cents"] < amount_cents:
        return json.dumps(
            {
                "error": (
                    f"Insufficient balance in '{source['name']}'. "
                    f"Available: {source['balance']}, requested: ${amount_dollars:.2f}."
                )
            }
        )

    # Stage the transfer
    transfer_id = str(uuid.uuid4())
    pending = {
        "source_id": source["id"],
        "source_name": source["name"],
        "source_type": source["type"],
        "destination_id": destination["id"],
        "destination_name": destination["name"],
        "destination_type": destination["type"],
        "amount_cents": amount_cents,
        "amount_display": f"${amount_dollars:.2f}",
        "created_at": time.time(),
        "user_id": user_id,
    }
    if note:
        pending["note"] = note
    pending_transfers[transfer_id] = pending

    if staged_this_turn is not None:
        staged_this_turn.append(transfer_id)

    if audit:
        audit.log(
            "transfer_staged",
            user_id=user_id,
            user_name=user_name,
            transfer_id=transfer_id,
            amount_cents=amount_cents,
            source=source["name"],
            destination=destination["name"],
            note=note or None,
        )

    log.info(
        "Transfer staged: %s -> %s for %s (id: %s)",
        source["name"],
        destination["name"],
        f"${amount_dollars:.2f}",
        transfer_id,
    )

    staged = {
        "pending_transfer_id": transfer_id,
        "source": source["name"],
        "destination": destination["name"],
        "amount": f"${amount_dollars:.2f}",
        "message": (
            "Transfer staged. The user will confirm or cancel via buttons in the chat."
        ),
    }
    if note:
        staged["note"] = note
    return json.dumps(staged)


def _handle_confirm_transfer(
    tool_input: dict[str, Any],
    client: SequenceClient,
    agent_config: AgentConfig,
    pending_transfers: dict[str, dict],
    sdk_config: SdkConfig | None = None,
) -> str:
    """Execute a previously staged transfer."""
    transfer_id = tool_input["pending_transfer_id"]

    if transfer_id not in pending_transfers:
        return json.dumps({"error": "No pending transfer found with that ID."})

    transfer = pending_transfers[transfer_id]

    # Check expiry
    elapsed = time.time() - transfer["created_at"]
    if elapsed > agent_config.pending_transfer_ttl:
        del pending_transfers[transfer_id]
        return json.dumps(
            {"error": "This transfer has expired. Please request a new transfer."}
        )

    # Execute the transfer via SDK
    kyc_id = sdk_config.kyc_id if sdk_config else None
    try:
        result = client.transfer(
            kyc_id,
            source_id=transfer["source_id"],
            destination_id=transfer["destination_id"],
            amount_cents=transfer["amount_cents"],
            source_type=transfer.get("source_type", "POD"),
            destination_type=transfer.get("destination_type", "POD"),
            description=transfer.get("note", ""),
        )
    except RuntimeError as e:
        del pending_transfers[transfer_id]
        return json.dumps({"error": str(e)})

    del pending_transfers[transfer_id]

    log.info(
        "Transfer executed: %s -> %s for %s",
        transfer["source_name"],
        transfer["destination_name"],
        transfer["amount_display"],
    )

    return json.dumps(
        {
            "success": True,
            "source": transfer["source_name"],
            "destination": transfer["destination_name"],
            "amount": transfer["amount_display"],
        }
    )


def _handle_cancel_transfer(
    tool_input: dict[str, Any],
    pending_transfers: dict[str, dict],
    *,
    user_id: int | None = None,
    audit: AuditLog | None = None,
) -> str:
    """Cancel a previously staged transfer."""
    transfer_id = tool_input["pending_transfer_id"]

    if transfer_id not in pending_transfers:
        return json.dumps({"error": "No pending transfer found with that ID."})

    transfer = pending_transfers[transfer_id]

    # Ownership check
    if user_id is not None and transfer.get("user_id") is not None:
        if transfer["user_id"] != user_id:
            return json.dumps({"error": "You can only cancel your own transfers."})

    if audit:
        audit.log(
            "transfer_cancelled",
            user_id=user_id,
            transfer_id=transfer_id,
            amount_cents=transfer["amount_cents"],
            source=transfer["source_name"],
            destination=transfer["destination_name"],
        )

    del pending_transfers[transfer_id]
    log.info("Transfer cancelled: %s", transfer_id)

    return json.dumps({"success": True, "cancelled": transfer_id})


def _handle_get_recent_activity(
    tool_input: dict[str, Any],
    client: SequenceClient,
    org_id: str | None = None,
) -> str:
    """Fetch recent transfer activity with optional filters."""
    count = tool_input.get("count", 10)
    statuses = None
    directions = None
    activity_types = None

    if "direction" in tool_input:
        directions = [tool_input["direction"]]
    if "status" in tool_input:
        statuses = [tool_input["status"]]
    if "activity_type" in tool_input:
        activity_types = [tool_input["activity_type"]]

    result = client.get_activity(
        org_id,
        first=count,
        statuses=statuses,
        directions=directions,
        activity_types=activity_types,
    )
    log.info("get_recent_activity returned %d transfers", len(result["transfers"]))
    return json.dumps(result)


def _handle_get_transfer_status(
    tool_input: dict[str, Any],
    client: SequenceClient,
    org_id: str | None = None,
) -> str:
    """Fetch detailed status of a single transfer."""
    transfer_id = tool_input["transfer_id"]
    result = client.get_transfer_detail(org_id, transfer_id)
    log.info("get_transfer_status(%s) -> %s", transfer_id, result.get("status"))
    return json.dumps(result)


def _handle_get_activity_summary(client: SequenceClient) -> str:
    """Fetch monthly activity summary."""
    result = client.get_activity_summary()
    log.info("get_activity_summary -> %d transfers", result["transfer_count"])
    return json.dumps(result)


def _handle_get_all_accounts(
    client: SequenceClient,
    org_id: str | None = None,
) -> str:
    """Fetch all account types: pods, ports, and external accounts."""
    result = client.get_all_accounts(org_id)
    log.info(
        "get_all_accounts -> %d pods, %d ports, %d accounts",
        len(result["pods"]),
        len(result["ports"]),
        len(result["accounts"]),
    )
    return json.dumps(result)


def _handle_save_memory(
    tool_input: dict[str, Any],
    memory: MemoryStore | None,
    user_name: str | None,
) -> str:
    """Save or update a fact in memory."""
    if memory is None:
        return json.dumps({"error": "Memory is not available."})

    content = tool_input["content"]
    fact_id = tool_input.get("fact_id")

    if fact_id:
        try:
            fact = memory.update(fact_id, content)
            return json.dumps({"success": True, "fact_id": fact.id, "updated": True})
        except KeyError:
            return json.dumps({"error": f"Fact '{fact_id}' not found."})

    try:
        fact = memory.save(content, created_by=user_name or "unknown")
        return json.dumps({"success": True, "fact_id": fact.id, "created": True})
    except ValueError as e:
        return json.dumps({"error": str(e)})


def _handle_delete_memory(
    tool_input: dict[str, Any],
    memory: MemoryStore | None,
) -> str:
    """Delete a fact from memory."""
    if memory is None:
        return json.dumps({"error": "Memory is not available."})

    fact_id = tool_input["fact_id"]
    try:
        memory.delete(fact_id)
        return json.dumps({"success": True, "deleted": fact_id})
    except KeyError:
        return json.dumps({"error": f"Fact '{fact_id}' not found."})


def _handle_list_memories(memory: MemoryStore | None) -> str:
    """List all facts in memory."""
    if memory is None:
        return json.dumps({"error": "Memory is not available."})

    facts = memory.facts
    return json.dumps(
        {
            "facts": [
                {"id": f.id, "content": f.content, "created_by": f.created_by}
                for f in facts
            ],
            "count": len(facts),
        }
    )
