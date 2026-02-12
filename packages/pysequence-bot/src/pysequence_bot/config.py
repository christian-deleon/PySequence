"""Configuration from environment variables and YAML config file.

Secrets (tokens, API keys) are always injected as environment variables,
typically via 1Password (``op run --env-file op.env``).

Non-secret settings (model, limits, system prompt, user mappings) live in
``bot-config.yaml``.  Resolution order:

1. ``BOT_CONFIG`` env var (explicit path)
2. ``BOT_DATA_DIR / "bot-config.yaml"`` (convention)
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("BOT_DATA_DIR", Path(__file__).resolve().parents[2]))


@dataclass
class SdkConfig:
    """Sequence SDK parameters needed by the bot."""

    org_id: str
    kyc_id: str


def get_sdk_config() -> SdkConfig:
    """Get Sequence SDK configuration from environment variables.

    Expected env vars: SEQUENCE_ORG_ID, SEQUENCE_KYC_ID
    """
    return SdkConfig(
        org_id=os.environ["SEQUENCE_ORG_ID"],
        kyc_id=os.environ["SEQUENCE_KYC_ID"],
    )


@dataclass
class AgentConfig:
    model: str
    system_prompt: str
    max_tokens: int = 1024
    max_history: int = 50
    trim_to: int = 40
    max_transfer_amount_cents: int = 1_000_000
    pending_transfer_ttl: int = 300
    conversation_ttl: int = 3600
    max_memory_facts: int = 100
    max_daily_transfer_cents: int = 2_500_000


@dataclass
class TelegramConfig:
    bot_token: str
    anthropic_api_key: str
    group_id: int
    user_names: dict[int, str]
    max_message_length: int = 2000
    rate_limit_messages: int = 10
    rate_limit_window_seconds: int = 60

    @property
    def allowed_user_ids(self) -> set[int]:
        return set(self.user_names.keys())


def _resolve_config_path() -> Path | None:
    """Find the config file, or return None if it doesn't exist."""
    explicit = os.environ.get("BOT_CONFIG")
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None
    default = DATA_DIR / "bot-config.yaml"
    return default if default.is_file() else None


def _parse_users(raw: Any) -> dict[int, str]:
    """Convert a YAML user mapping (possibly str-keyed) to {int: str}."""
    if not isinstance(raw, dict):
        return {}
    return {int(k): str(v) for k, v in raw.items()}


def load_config() -> tuple[AgentConfig, TelegramConfig]:
    """Load bot configuration from YAML merged with env var secrets.

    The config file is required — the bot cannot start without it because it
    contains the system prompt, user mappings, and group ID.

    Secrets always come from env vars: ``TELEGRAM_BOT_TOKEN``, ``ANTHROPIC_API_KEY``.
    """
    path = _resolve_config_path()
    if path is None:
        raise FileNotFoundError(
            "bot-config.yaml not found. Set BOT_CONFIG or place it in BOT_DATA_DIR."
        )

    log.info("Loading config from %s", path)
    with open(path) as f:
        cfg: dict[str, Any] = yaml.safe_load(f) or {}

    agent_section: dict[str, Any] = cfg.get("agent", {})
    safeguards_section: dict[str, Any] = cfg.get("safeguards", {})
    telegram_section: dict[str, Any] = cfg.get("telegram", {})
    memory_section: dict[str, Any] = cfg.get("memory", {})

    if "model" not in agent_section:
        raise ValueError("agent.model is required in bot-config.yaml")
    if "system_prompt" not in cfg:
        raise ValueError("system_prompt is required in bot-config.yaml")
    if "group_id" not in telegram_section:
        raise ValueError("telegram.group_id is required in bot-config.yaml")
    users = _parse_users(telegram_section.get("users", {}))
    if not users:
        raise ValueError("telegram.users is required in bot-config.yaml")

    agent_config = AgentConfig(
        model=agent_section["model"],
        system_prompt=cfg["system_prompt"],
        max_tokens=agent_section.get("max_tokens", AgentConfig.max_tokens),
        max_history=agent_section.get("max_history", AgentConfig.max_history),
        trim_to=agent_section.get("trim_to", AgentConfig.trim_to),
        conversation_ttl=agent_section.get(
            "conversation_ttl", AgentConfig.conversation_ttl
        ),
        max_transfer_amount_cents=safeguards_section.get(
            "max_transfer_cents", AgentConfig.max_transfer_amount_cents
        ),
        max_daily_transfer_cents=safeguards_section.get(
            "max_daily_transfer_cents", AgentConfig.max_daily_transfer_cents
        ),
        pending_transfer_ttl=safeguards_section.get(
            "pending_transfer_ttl", AgentConfig.pending_transfer_ttl
        ),
        max_memory_facts=memory_section.get(
            "max_facts", AgentConfig.max_memory_facts
        ),
    )

    telegram_config = TelegramConfig(
        bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        group_id=telegram_section["group_id"],
        user_names=users,
        max_message_length=telegram_section.get("max_message_length", 2000),
        rate_limit_messages=telegram_section.get("rate_limit_messages", 10),
        rate_limit_window_seconds=telegram_section.get(
            "rate_limit_window_seconds", 60
        ),
    )

    return agent_config, telegram_config
