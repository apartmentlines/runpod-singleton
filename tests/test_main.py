import pytest
import sys
import argparse
from pathlib import Path
from unittest.mock import patch, MagicMock

from runpod_singleton.singleton import main, RunpodSingletonManager
from runpod_singleton import constants as const


@pytest.fixture
def mock_args() -> argparse.Namespace:
    """Fixture to create a mock argparse.Namespace object with default flags."""
    args = argparse.Namespace()
    args.config = MagicMock(spec=Path)
    args.api_key = "test_api_key_arg"
    args.count = False  # Default to False for most tests
    args.stop = False  # Default to False
    args.terminate = False  # Default to False
    args.debug = False  # Default to False
    return args


@patch("runpod_singleton.singleton.parse_args")
@patch("runpod_singleton.singleton.RunpodSingletonManager")
@patch("runpod_singleton.singleton.sys.exit")
def test_main_success(
    mock_exit: MagicMock,
    mock_manager_class: MagicMock,
    mock_parse_args: MagicMock,
    mock_args: argparse.Namespace,
):
    """Test main execution path when manager.run() succeeds."""
    mock_parse_args.return_value = mock_args
    mock_manager_instance = MagicMock(spec=RunpodSingletonManager)
    # Simulate successful run returning a pod ID (truthy)
    mock_manager_instance.run.return_value = "pod-id-123"
    mock_manager_class.return_value = mock_manager_instance

    main()

    mock_parse_args.assert_called_once()
    mock_manager_class.assert_called_once_with(
        mock_args.config, mock_args.api_key, mock_args.stop, mock_args.terminate, mock_args.debug
    )
    mock_manager_instance.run.assert_called_once()
    mock_exit.assert_called_once_with(const.EXIT_SUCCESS)


@patch("runpod_singleton.singleton.parse_args")
@patch("runpod_singleton.singleton.RunpodSingletonManager")
@patch("runpod_singleton.singleton.sys.exit")
def test_main_failure_run_returns_false(
    mock_exit: MagicMock,
    mock_manager_class: MagicMock,
    mock_parse_args: MagicMock,
    mock_args: argparse.Namespace,
):
    """Test main execution path when manager.run() returns None (failure)."""
    mock_parse_args.return_value = mock_args
    mock_manager_instance = MagicMock(spec=RunpodSingletonManager)
    mock_manager_instance.run.return_value = None
    mock_manager_class.return_value = mock_manager_instance

    main()

    mock_parse_args.assert_called_once()
    mock_manager_class.assert_called_once_with(
        mock_args.config, mock_args.api_key, mock_args.stop, mock_args.terminate, mock_args.debug
    )
    mock_manager_instance.run.assert_called_once()
    mock_exit.assert_called_once_with(const.EXIT_FAILURE)


@patch("runpod_singleton.singleton.parse_args")
@patch("runpod_singleton.singleton.RunpodSingletonManager")
@patch("runpod_singleton.singleton.sys.exit")
@patch("builtins.print") # Mock print for checking error output
def test_main_exception_during_init(
    mock_print: MagicMock,
    mock_exit: MagicMock,
    mock_manager_class: MagicMock,
    mock_parse_args: MagicMock,
    mock_args: argparse.Namespace,
):
    """Test main handles exception during RunpodSingletonManager initialization."""
    mock_parse_args.return_value = mock_args
    init_exception = RuntimeError("Failed to initialize manager")
    mock_manager_class.side_effect = init_exception # Raise error on instantiation

    main()

    mock_parse_args.assert_called_once()
    mock_manager_class.assert_called_once_with( # Still attempts to init
        mock_args.config, mock_args.api_key, mock_args.stop, mock_args.terminate, mock_args.debug
    )
    # Assert run() was NOT called on the (non-existent) instance
    assert mock_manager_class.return_value.run.call_count == 0
    mock_exit.assert_called_once_with(const.EXIT_FAILURE)
    # Check that print was called with the error message to stderr
    mock_print.assert_called_once()
    assert str(init_exception) in mock_print.call_args[0][0]
    assert mock_print.call_args[1].get("file") == sys.stderr


@patch("runpod_singleton.singleton.parse_args")
@patch("runpod_singleton.singleton.RunpodSingletonManager")
@patch("runpod_singleton.singleton.sys.exit")
@patch("builtins.print") # Mock print for checking error output
def test_main_exception_during_run(
    mock_print: MagicMock,
    mock_exit: MagicMock,
    mock_manager_class: MagicMock,
    mock_parse_args: MagicMock,
    mock_args: argparse.Namespace,
):
    """Test main handles exception during manager.run()."""
    mock_parse_args.return_value = mock_args
    mock_manager_instance = MagicMock(spec=RunpodSingletonManager)
    run_exception = ValueError("Error during run")
    mock_manager_instance.run.side_effect = run_exception # Raise error on run()
    mock_manager_class.return_value = mock_manager_instance

    main()

    mock_parse_args.assert_called_once()
    mock_manager_class.assert_called_once_with(
        mock_args.config, mock_args.api_key, mock_args.stop, mock_args.terminate, mock_args.debug
    )
    mock_manager_instance.run.assert_called_once() # run() is called
    mock_exit.assert_called_once_with(const.EXIT_FAILURE)
    # Check that print was called with the error message to stderr
    mock_print.assert_called_once()
    assert str(run_exception) in mock_print.call_args[0][0]
    assert mock_print.call_args[1].get("file") == sys.stderr


@patch("runpod_singleton.singleton.parse_args")
@patch("runpod_singleton.singleton.RunpodSingletonManager")
@patch("runpod_singleton.singleton.sys.exit")
@patch("builtins.print")
def test_main_count_mode_success(
    mock_print: MagicMock,
    mock_exit: MagicMock,
    mock_manager_class: MagicMock,
    mock_parse_args: MagicMock,
    mock_args: argparse.Namespace,
):
    """Test main execution path when --count is specified and succeeds."""
    # Set args for count mode
    mock_args.count = True
    mock_args.stop = False
    mock_args.terminate = False
    mock_parse_args.return_value = mock_args

    # Mock manager instance and its methods/attributes needed
    mock_manager_instance = MagicMock(spec=RunpodSingletonManager)
    expected_counts = {"total": 3, "running": 1}
    mock_manager_instance.count_pods.return_value = expected_counts
    # Mock config access for print statement
    mock_manager_instance.config = {const.POD_NAME: "test-pod-name"}
    mock_manager_class.return_value = mock_manager_instance

    main()

    mock_parse_args.assert_called_once()
    mock_manager_class.assert_called_once_with(
        mock_args.config, mock_args.api_key, mock_args.stop, mock_args.terminate, mock_args.debug
    )
    mock_manager_instance.count_pods.assert_called_once()
    mock_manager_instance.run.assert_not_called() # run() should not be called in count mode
    # Check print output
    expected_output = "Pods matching name 'test-pod-name': Total=3, Running=1"
    mock_print.assert_called_once_with(expected_output)
    mock_exit.assert_called_once_with(const.EXIT_SUCCESS)


@patch("runpod_singleton.singleton.parse_args")
@patch("runpod_singleton.singleton.RunpodSingletonManager")
@patch("runpod_singleton.singleton.sys.exit")
@patch("builtins.print")
def test_main_count_mode_failure(
    mock_print: MagicMock,
    mock_exit: MagicMock,
    mock_manager_class: MagicMock,
    mock_parse_args: MagicMock,
    mock_args: argparse.Namespace,
):
    """Test main handles failure (False return) from manager.count_pods()."""
    mock_args.count = True
    mock_args.stop = False
    mock_args.terminate = False
    mock_parse_args.return_value = mock_args

    mock_manager_instance = MagicMock(spec=RunpodSingletonManager)
    mock_manager_instance.count_pods.return_value = None
    mock_manager_class.return_value = mock_manager_instance

    main()

    mock_parse_args.assert_called_once()
    mock_manager_class.assert_called_once_with(
        mock_args.config, mock_args.api_key, mock_args.stop, mock_args.terminate, mock_args.debug
    )
    mock_manager_instance.count_pods.assert_called_once()
    mock_manager_instance.run.assert_not_called() # run() should not be called
    # Check that the success print was NOT called
    mock_print.assert_not_called()
    mock_exit.assert_called_once_with(const.EXIT_FAILURE)
