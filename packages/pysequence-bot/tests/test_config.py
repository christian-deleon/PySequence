"""Unit tests for pysequence_bot.config."""

import pytest
import yaml

from pysequence_bot.config import (
    SdkConfig,
    get_sdk_config,
    load_config,
)

# Minimal config that satisfies all required fields
_REQUIRED = {
    "agent": {"model": "claude-opus-4-6"},
    "telegram": {"group_id": -100999, "users": {12345: "Alice"}},
    "system_prompt": "You are a test bot.",
}


def _merge(overrides: dict) -> dict:
    """Deep-merge overrides into the required config."""
    merged = {**_REQUIRED, **overrides}
    for key in ("agent", "telegram"):
        if key in overrides:
            merged[key] = {**_REQUIRED[key], **overrides[key]}
    return merged


class TestGetSdkConfig:
    def test_reads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SEQUENCE_ORG_ID", "org-123")
        monkeypatch.setenv("SEQUENCE_KYC_ID", "kyc-456")

        cfg = get_sdk_config()

        assert isinstance(cfg, SdkConfig)
        assert cfg.org_id == "org-123"
        assert cfg.kyc_id == "kyc-456"

    def test_raises_on_missing_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SEQUENCE_ORG_ID", raising=False)
        monkeypatch.delenv("SEQUENCE_KYC_ID", raising=False)

        with pytest.raises(KeyError):
            get_sdk_config()


class TestLoadConfig:
    """Tests for load_config() YAML + env var merging."""

    def _set_secrets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-xxx")

    def _write_config(self, tmp_path, overrides: dict | None = None):
        """Write a YAML config file with required fields, optionally overridden."""
        data = _merge(overrides or {})
        cfg_path = tmp_path / "bot-config.yaml"
        cfg_path.write_text(yaml.dump(data))
        return cfg_path

    def test_raises_without_config_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        self._set_secrets(monkeypatch)
        monkeypatch.setenv("BOT_CONFIG", str(tmp_path / "nope.yaml"))

        with pytest.raises(FileNotFoundError):
            load_config()

    def test_raises_without_model(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        self._set_secrets(monkeypatch)
        cfg_path = tmp_path / "bot-config.yaml"
        data = {**_REQUIRED}
        data["agent"] = {}
        cfg_path.write_text(yaml.dump(data))
        monkeypatch.setenv("BOT_CONFIG", str(cfg_path))

        with pytest.raises(ValueError, match="model"):
            load_config()

    def test_raises_without_system_prompt(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        self._set_secrets(monkeypatch)
        cfg_path = tmp_path / "bot-config.yaml"
        data = {k: v for k, v in _REQUIRED.items() if k != "system_prompt"}
        cfg_path.write_text(yaml.dump(data))
        monkeypatch.setenv("BOT_CONFIG", str(cfg_path))

        with pytest.raises(ValueError, match="system_prompt"):
            load_config()

    def test_raises_without_group_id(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        self._set_secrets(monkeypatch)
        cfg_path = tmp_path / "bot-config.yaml"
        data = {**_REQUIRED, "telegram": {"users": {12345: "Alice"}}}
        cfg_path.write_text(yaml.dump(data))
        monkeypatch.setenv("BOT_CONFIG", str(cfg_path))

        with pytest.raises(ValueError, match="group_id"):
            load_config()

    def test_raises_without_users(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        self._set_secrets(monkeypatch)
        cfg_path = tmp_path / "bot-config.yaml"
        data = {**_REQUIRED, "telegram": {"group_id": -100999}}
        cfg_path.write_text(yaml.dump(data))
        monkeypatch.setenv("BOT_CONFIG", str(cfg_path))

        with pytest.raises(ValueError, match="users"):
            load_config()

    def test_full_yaml(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        self._set_secrets(monkeypatch)
        cfg_path = tmp_path / "bot-config.yaml"
        cfg_path.write_text(
            yaml.dump(
                {
                    "agent": {
                        "model": "claude-sonnet-4-5-20250929",
                        "max_tokens": 2048,
                        "max_history": 100,
                        "trim_to": 80,
                        "conversation_ttl": 7200,
                    },
                    "safeguards": {
                        "max_transfer_cents": 500_000,
                        "max_daily_transfer_cents": 1_000_000,
                        "pending_transfer_ttl": 600,
                    },
                    "telegram": {
                        "group_id": -100999,
                        "users": {12345: "Alice", 67890: "Bob"},
                        "rate_limit_messages": 5,
                        "rate_limit_window_seconds": 30,
                        "max_message_length": 4000,
                    },
                    "memory": {"max_facts": 50},
                    "system_prompt": "Custom prompt",
                }
            )
        )
        monkeypatch.setenv("BOT_CONFIG", str(cfg_path))

        agent, telegram = load_config()

        assert agent.model == "claude-sonnet-4-5-20250929"
        assert agent.max_tokens == 2048
        assert agent.max_history == 100
        assert agent.trim_to == 80
        assert agent.conversation_ttl == 7200
        assert agent.max_transfer_amount_cents == 500_000
        assert agent.max_daily_transfer_cents == 1_000_000
        assert agent.pending_transfer_ttl == 600
        assert agent.max_memory_facts == 50
        assert agent.system_prompt == "Custom prompt"
        assert telegram.group_id == -100999
        assert telegram.user_names == {12345: "Alice", 67890: "Bob"}
        assert telegram.rate_limit_messages == 5
        assert telegram.rate_limit_window_seconds == 30
        assert telegram.max_message_length == 4000

    def test_optional_fields_use_defaults(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        self._set_secrets(monkeypatch)
        cfg_path = self._write_config(tmp_path)
        monkeypatch.setenv("BOT_CONFIG", str(cfg_path))

        agent, telegram = load_config()

        assert agent.max_tokens == 1024
        assert agent.max_history == 50
        assert agent.conversation_ttl == 3600
        assert agent.max_transfer_amount_cents == 1_000_000
        assert agent.max_daily_transfer_cents == 2_500_000
        assert agent.pending_transfer_ttl == 300
        assert agent.max_memory_facts == 100
        assert telegram.rate_limit_messages == 10
        assert telegram.rate_limit_window_seconds == 60
        assert telegram.max_message_length == 2000

    def test_secrets_from_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "my-secret-token")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")
        cfg_path = self._write_config(tmp_path)
        monkeypatch.setenv("BOT_CONFIG", str(cfg_path))

        _, telegram = load_config()

        assert telegram.bot_token == "my-secret-token"
        assert telegram.anthropic_api_key == "sk-ant-secret"

    def test_secrets_required(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        cfg_path = self._write_config(tmp_path)
        monkeypatch.setenv("BOT_CONFIG", str(cfg_path))

        with pytest.raises(KeyError):
            load_config()

    def test_yaml_user_mapping_string_keys(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """YAML may parse integer keys as strings; they should be coerced."""
        self._set_secrets(monkeypatch)
        cfg_path = tmp_path / "bot-config.yaml"
        cfg_path.write_text(
            "agent:\n"
            "  model: claude-opus-4-6\n"
            "system_prompt: test\n"
            "telegram:\n"
            "  group_id: -100999\n"
            "  users:\n"
            '    "12345": Alice\n'
            '    "67890": Bob\n'
        )
        monkeypatch.setenv("BOT_CONFIG", str(cfg_path))

        _, telegram = load_config()

        assert telegram.user_names == {12345: "Alice", 67890: "Bob"}
        assert telegram.allowed_user_ids == {12345, 67890}

    def test_data_dir_fallback(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        """When BOT_CONFIG is not set, falls back to DATA_DIR / bot-config.yaml."""
        self._set_secrets(monkeypatch)
        monkeypatch.delenv("BOT_CONFIG", raising=False)
        self._write_config(tmp_path, {"agent": {"model": "custom-model"}})

        import pysequence_bot.config as config_mod

        monkeypatch.setattr(config_mod, "DATA_DIR", tmp_path)

        agent, _ = load_config()
        assert agent.model == "custom-model"
