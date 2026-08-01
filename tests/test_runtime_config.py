from __future__ import annotations

import pytest

from app.shared.runtime_config import (
    DEFAULT_LOG_CONSOLE_LEVEL,
    DEFAULT_LOG_FILE_LEVEL,
    DEFAULT_LOG_FILE_PATH,
    ENV_LOG_CONSOLE_LEVEL,
    ENV_LOG_ENABLED_AREAS,
    ENV_LOG_FILE_LEVEL,
    ENV_LOG_FILE_PATH,
    StartupConfig,
    StartupConfigurationError,
)


class TestStartupConfig:
    def test_from_env_uses_existing_defaults(self):
        config = StartupConfig.from_env({})

        assert config.console_level == DEFAULT_LOG_CONSOLE_LEVEL
        assert config.file_level == DEFAULT_LOG_FILE_LEVEL
        assert config.log_file_path == DEFAULT_LOG_FILE_PATH
        assert config.enabled_areas is None

    def test_from_env_normalizes_valid_overrides(self, tmp_path):
        config = StartupConfig.from_env(
            {
                ENV_LOG_CONSOLE_LEVEL: "warning",
                ENV_LOG_FILE_LEVEL: "error",
                ENV_LOG_FILE_PATH: str(tmp_path / "custom.log"),
                ENV_LOG_ENABLED_AREAS: " UI->PlaybackHandler, Main ,Main ",
            }
        )

        assert config.console_level == "WARNING"
        assert config.file_level == "ERROR"
        assert config.log_file_path == str(tmp_path / "custom.log")
        assert config.enabled_areas == ("UI->PlaybackHandler", "Main")

    def test_from_env_rejects_invalid_console_level(self):
        with pytest.raises(StartupConfigurationError, match=ENV_LOG_CONSOLE_LEVEL):
            StartupConfig.from_env({ENV_LOG_CONSOLE_LEVEL: "verbose"})

    def test_from_env_rejects_blank_log_file_path(self):
        with pytest.raises(StartupConfigurationError, match=ENV_LOG_FILE_PATH):
            StartupConfig.from_env({ENV_LOG_FILE_PATH: "   "})

    def test_from_env_treats_blank_enabled_areas_as_no_filter(self):
        config = StartupConfig.from_env({ENV_LOG_ENABLED_AREAS: " , , "})

        assert config.enabled_areas is None

