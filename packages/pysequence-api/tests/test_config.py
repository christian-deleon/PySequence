"""Unit tests for pysequence_api.config."""

import pytest

from pysequence_api.config import ServerConfig, get_server_config


class TestGetServerConfig:
    def test_reads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SEQUENCE_API_KEY", "my-secret-key")

        cfg = get_server_config()

        assert isinstance(cfg, ServerConfig)
        assert cfg.api_key == "my-secret-key"
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 8720
        assert cfg.max_transfer_cents == 1_000_000
        assert cfg.max_daily_transfer_cents == 2_500_000

    def test_custom_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SEQUENCE_API_KEY", "key-123")
        monkeypatch.setenv("SEQUENCE_SERVER_HOST", "127.0.0.1")
        monkeypatch.setenv("SEQUENCE_SERVER_PORT", "9000")
        monkeypatch.setenv("SEQUENCE_MAX_TRANSFER_CENTS", "500000")
        monkeypatch.setenv("SEQUENCE_MAX_DAILY_TRANSFER_CENTS", "1000000")

        cfg = get_server_config()

        assert cfg.host == "127.0.0.1"
        assert cfg.port == 9000
        assert cfg.max_transfer_cents == 500_000
        assert cfg.max_daily_transfer_cents == 1_000_000

    def test_raises_on_missing_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SEQUENCE_API_KEY", raising=False)

        with pytest.raises(KeyError):
            get_server_config()
