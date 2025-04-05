import pytest
import os
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Any

from runpod_singleton.singleton import (
    RunpodSingletonManager,
    RunpodApiClient,
    PodLifecycleManager,
)
from runpod_singleton import constants as const


# --- Fixtures ---

@pytest.fixture
def mock_config_path() -> MagicMock:
    """Fixture for a mocked Path object for config."""
    return MagicMock(spec=Path)


@pytest.fixture
def sample_loaded_config() -> dict[str, Any]:
    """Fixture for a sample configuration dictionary returned by load_config."""
    return {
        const.POD_NAME: "test-singleton-pod",
        const.IMAGE_NAME: "test-image",
        const.GPU_TYPES: ["NVIDIA GeForce RTX 3090"],
    }


@pytest.fixture
def mock_logger_instance() -> MagicMock:
    """Fixture for a mocked Logger instance."""
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def mock_api_client_instance() -> MagicMock:
    """Fixture for a mocked RunpodApiClient instance."""
    return MagicMock(spec=RunpodApiClient)


@pytest.fixture
def mock_pod_lifecycle_manager_instance() -> MagicMock:
    """Fixture for a mocked PodLifecycleManager instance."""
    return MagicMock(spec=PodLifecycleManager)


@pytest.fixture(autouse=True)
def mock_dependencies():
    """Auto-used fixture to mock dependencies for RunpodSingletonManager tests."""
    with patch("runpod_singleton.singleton.load_config", autospec=True) as mock_load, \
         patch("runpod_singleton.singleton.Logger", autospec=True) as mock_logger_class, \
         patch("runpod_singleton.singleton.RunpodApiClient", autospec=True) as mock_api_client_class, \
         patch("runpod_singleton.singleton.PodLifecycleManager", autospec=True) as mock_plm_class, \
         patch.dict(os.environ, {}, clear=True): # Clear environment variables
        # Configure mocks to return specific instances when called
        mock_logger_class.return_value = MagicMock(spec=logging.Logger)
        mock_api_client_class.return_value = MagicMock(spec=RunpodApiClient)
        mock_plm_class.return_value = MagicMock(spec=PodLifecycleManager)
        yield {
            "load_config": mock_load,
            "Logger": mock_logger_class,
            "RunpodApiClient": mock_api_client_class,
            "PodLifecycleManager": mock_plm_class,
        }


# --- Test Cases ---

def test_init_success_api_key_arg(
    mock_dependencies: dict[str, MagicMock],
    mock_config_path: MagicMock,
    sample_loaded_config: dict[str, Any],
):
    """Test successful initialization with API key from argument."""
    api_key = "arg_api_key"
    mock_dependencies["load_config"].return_value = sample_loaded_config

    manager = RunpodSingletonManager(
        config_path=mock_config_path, api_key=api_key, debug=True
    )

    mock_dependencies["Logger"].assert_called_once_with(
        "RunpodSingletonManager", debug=True
    )
    mock_dependencies["load_config"].assert_called_once_with(mock_config_path)
    mock_dependencies["RunpodApiClient"].assert_called_once_with(api_key=api_key)
    assert manager.config is sample_loaded_config
    assert manager.log is mock_dependencies["Logger"].return_value
    assert manager.client is mock_dependencies["RunpodApiClient"].return_value
    assert manager.stop is False
    assert manager.terminate is False
    assert manager.debug is True


@patch.dict(os.environ, {"RUNPOD_API_KEY": "env_api_key"}, clear=True)
def test_init_success_api_key_env(
    mock_dependencies: dict[str, MagicMock],
    mock_config_path: MagicMock,
    sample_loaded_config: dict[str, Any],
):
    """Test successful initialization with API key from environment."""
    mock_dependencies["load_config"].return_value = sample_loaded_config

    manager = RunpodSingletonManager(
        config_path=mock_config_path, api_key=None, stop=True, terminate=True
    )

    mock_dependencies["Logger"].assert_called_once_with(
        "RunpodSingletonManager", debug=False
    )
    mock_dependencies["load_config"].assert_called_once_with(mock_config_path)
    mock_dependencies["RunpodApiClient"].assert_called_once_with(api_key="env_api_key")
    assert manager.config is sample_loaded_config
    assert manager.log is mock_dependencies["Logger"].return_value
    assert manager.client is mock_dependencies["RunpodApiClient"].return_value
    assert manager.stop is True
    assert manager.terminate is True
    assert manager.debug is False


def test_init_api_key_precedence(
    mock_dependencies: dict[str, MagicMock],
    mock_config_path: MagicMock,
    sample_loaded_config: dict[str, Any],
):
    """Test API key argument takes precedence over environment variable."""
    api_key_arg = "arg_api_key"
    with patch.dict(os.environ, {"RUNPOD_API_KEY": "env_api_key"}, clear=True):
        mock_dependencies["load_config"].return_value = sample_loaded_config
        manager = RunpodSingletonManager(
            config_path=mock_config_path, api_key=api_key_arg
        )
        mock_dependencies["RunpodApiClient"].assert_called_once_with(api_key=api_key_arg)


def test_init_no_api_key_raises_error(
    mock_dependencies: dict[str, MagicMock],
    mock_config_path: MagicMock,
    sample_loaded_config: dict[str, Any],
):
    """Test initialization raises RuntimeError if no API key is found."""
    # No arg, no env var
    mock_dependencies["load_config"].return_value = sample_loaded_config
    with pytest.raises(RuntimeError, match="RunPod API key not found"):
        RunpodSingletonManager(config_path=mock_config_path, api_key=None)


def test_init_load_config_error(
    mock_dependencies: dict[str, MagicMock], mock_config_path: MagicMock
):
    """Test initialization propagates exceptions from load_config."""
    mock_dependencies["load_config"].side_effect = FileNotFoundError("File not found")
    with pytest.raises(FileNotFoundError):
        RunpodSingletonManager(config_path=mock_config_path, api_key="dummy_key")


# --- run() Method Tests ---

def test_run_calls_manage_when_no_flags(
    mock_dependencies: dict[str, MagicMock],
    mock_config_path: MagicMock,
    sample_loaded_config: dict[str, Any],
    mock_pod_lifecycle_manager_instance: MagicMock,
):
    """Test run() calls PodLifecycleManager.manage() when stop/terminate are False."""
    api_key = "test_key"
    mock_dependencies["load_config"].return_value = sample_loaded_config
    api_key = "test_key"
    expected_pod_id = "pod-123-success"
    mock_dependencies["load_config"].return_value = sample_loaded_config
    mock_dependencies["PodLifecycleManager"].return_value = mock_pod_lifecycle_manager_instance
    mock_pod_lifecycle_manager_instance.manage.return_value = expected_pod_id

    manager = RunpodSingletonManager(
        config_path=mock_config_path, api_key=api_key, stop=False, terminate=False
    )
    result = manager.run()

    mock_dependencies["PodLifecycleManager"].assert_called_once_with(
        manager.client, manager.config, manager.log, False, False
    )
    mock_pod_lifecycle_manager_instance.manage.assert_called_once()
    mock_pod_lifecycle_manager_instance.perform_cleanup_actions.assert_not_called()
    assert result == expected_pod_id


def test_run_calls_cleanup_when_stop_flag(
    mock_dependencies: dict[str, MagicMock],
    mock_config_path: MagicMock,
    sample_loaded_config: dict[str, Any],
    mock_pod_lifecycle_manager_instance: MagicMock,
):
    """Test run() calls PodLifecycleManager.perform_cleanup_actions() when stop=True."""
    api_key = "test_key"
    mock_dependencies["load_config"].return_value = sample_loaded_config
    mock_dependencies["PodLifecycleManager"].return_value = mock_pod_lifecycle_manager_instance
    mock_pod_lifecycle_manager_instance.perform_cleanup_actions.return_value = True # Simulate success

    manager = RunpodSingletonManager(
        config_path=mock_config_path, api_key=api_key, stop=True, terminate=False
    )
    result = manager.run()

    mock_dependencies["PodLifecycleManager"].assert_called_once_with(
        manager.client, manager.config, manager.log, True, False
    )
    mock_pod_lifecycle_manager_instance.manage.assert_not_called()
    mock_pod_lifecycle_manager_instance.perform_cleanup_actions.assert_called_once()
    assert result is True


def test_run_calls_cleanup_when_terminate_flag(
    mock_dependencies: dict[str, MagicMock],
    mock_config_path: MagicMock,
    sample_loaded_config: dict[str, Any],
    mock_pod_lifecycle_manager_instance: MagicMock,
):
    """Test run() calls PodLifecycleManager.perform_cleanup_actions() when terminate=True."""
    api_key = "test_key"
    mock_dependencies["load_config"].return_value = sample_loaded_config
    mock_dependencies["PodLifecycleManager"].return_value = mock_pod_lifecycle_manager_instance
    mock_pod_lifecycle_manager_instance.perform_cleanup_actions.return_value = False # Simulate failure

    manager = RunpodSingletonManager(
        config_path=mock_config_path, api_key=api_key, stop=False, terminate=True
    )
    result = manager.run()

    mock_dependencies["PodLifecycleManager"].assert_called_once_with(
        manager.client, manager.config, manager.log, False, True
    )
    mock_pod_lifecycle_manager_instance.manage.assert_not_called()
    mock_pod_lifecycle_manager_instance.perform_cleanup_actions.assert_called_once()
    assert result is False # Check return value propagation


def test_run_calls_cleanup_when_both_flags(
    mock_dependencies: dict[str, MagicMock],
    mock_config_path: MagicMock,
    sample_loaded_config: dict[str, Any],
    mock_pod_lifecycle_manager_instance: MagicMock,
):
    """Test run() calls PodLifecycleManager.perform_cleanup_actions() when stop=True and terminate=True."""
    api_key = "test_key"
    mock_dependencies["load_config"].return_value = sample_loaded_config
    mock_dependencies["PodLifecycleManager"].return_value = mock_pod_lifecycle_manager_instance
    mock_pod_lifecycle_manager_instance.perform_cleanup_actions.return_value = True

    manager = RunpodSingletonManager(
        config_path=mock_config_path, api_key=api_key, stop=True, terminate=True
    )
    result = manager.run()

    mock_dependencies["PodLifecycleManager"].assert_called_once_with(
        manager.client, manager.config, manager.log, True, True
    )
    mock_pod_lifecycle_manager_instance.manage.assert_not_called()
    mock_pod_lifecycle_manager_instance.perform_cleanup_actions.assert_called_once()
    assert result is True


def test_run_catches_exception_in_manage(
    mock_dependencies: dict[str, MagicMock],
    mock_config_path: MagicMock,
    sample_loaded_config: dict[str, Any],
    mock_pod_lifecycle_manager_instance: MagicMock,
    mock_logger_instance: MagicMock,
):
    """Test run() catches exceptions from manage(), logs, and returns False."""
    api_key = "test_key"
    mock_dependencies["load_config"].return_value = sample_loaded_config
    mock_dependencies["Logger"].return_value = mock_logger_instance # Use specific logger mock
    mock_dependencies["PodLifecycleManager"].return_value = mock_pod_lifecycle_manager_instance
    error_message = "Unexpected error during manage"
    mock_pod_lifecycle_manager_instance.manage.side_effect = Exception(error_message)

    manager = RunpodSingletonManager(
        config_path=mock_config_path, api_key=api_key, stop=False, terminate=False, debug=True
    )
    result = manager.run()

    mock_pod_lifecycle_manager_instance.manage.assert_called_once()
    mock_logger_instance.error.assert_called_once_with(
        f"An unexpected error occurred during execution: {error_message}",
        exc_info=True
    )
    assert result is False # Expect False on exception


def test_run_catches_exception_in_cleanup(
    mock_dependencies: dict[str, MagicMock],
    mock_config_path: MagicMock,
    sample_loaded_config: dict[str, Any],
    mock_pod_lifecycle_manager_instance: MagicMock,
    mock_logger_instance: MagicMock,
):
    """Test run() catches exceptions from perform_cleanup_actions(), logs, and returns False."""
    api_key = "test_key"
    mock_dependencies["load_config"].return_value = sample_loaded_config
    mock_dependencies["Logger"].return_value = mock_logger_instance # Use specific logger mock
    mock_dependencies["PodLifecycleManager"].return_value = mock_pod_lifecycle_manager_instance
    error_message = "Unexpected error during cleanup"
    mock_pod_lifecycle_manager_instance.perform_cleanup_actions.side_effect = Exception(error_message)

    manager = RunpodSingletonManager(
        config_path=mock_config_path, api_key=api_key, stop=True, terminate=False
    )
    result = manager.run()

    mock_pod_lifecycle_manager_instance.perform_cleanup_actions.assert_called_once()
    mock_logger_instance.error.assert_called_once()
    assert error_message in mock_logger_instance.error.call_args[0][0]
    assert result is False
