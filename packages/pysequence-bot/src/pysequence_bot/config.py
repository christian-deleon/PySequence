"""Configuration from environment variables.

All secrets are injected as environment variables at runtime,
typically via 1Password (``op run --env-file op.env``).
"""

import os
from dataclasses import dataclass
from pathlib import Path

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
    model: str = "claude-opus-4-6"
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


def get_telegram_config() -> TelegramConfig:
    """Get Telegram bot configuration from environment variables.

    Expected env vars: TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY,
    TELEGRAM_USER_NAMES (comma-separated id:name pairs, e.g. "12345:Alice,67890:Bob"),
    TELEGRAM_GROUP_ID
    """
    user_names: dict[int, str] = {}
    for pair in os.environ["TELEGRAM_USER_NAMES"].split(","):
        uid, name = pair.strip().split(":", 1)
        user_names[int(uid.strip())] = name.strip()

    return TelegramConfig(
        bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        group_id=int(os.environ["TELEGRAM_GROUP_ID"]),
        user_names=user_names,
    )
