"""Unit tests for pysequence_bot.config."""

import pytest

from pysequence_bot.config import (
    SdkConfig,
    TelegramConfig,
    get_sdk_config,
    get_telegram_config,
)


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


class TestGetTelegramConfig:
    def _set_required_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-xxx")
        monkeypatch.setenv("TELEGRAM_USER_NAMES", "12345:Alice,67890:Bob")
        monkeypatch.setenv("TELEGRAM_GROUP_ID", "-100999")

    def test_parses_user_names(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._set_required_env(monkeypatch)

        cfg = get_telegram_config()

        assert isinstance(cfg, TelegramConfig)
        assert cfg.user_names == {12345: "Alice", 67890: "Bob"}

    def test_allowed_user_ids_derived_from_user_names(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._set_required_env(monkeypatch)

        cfg = get_telegram_config()

        assert cfg.allowed_user_ids == {12345, 67890}

    def test_raises_on_missing_user_names(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._set_required_env(monkeypatch)
        monkeypatch.delenv("TELEGRAM_USER_NAMES")

        with pytest.raises(KeyError):
            get_telegram_config()
