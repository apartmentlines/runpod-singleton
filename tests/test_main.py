import pytest
import sys
import argparse
from pathlib import Path
from unittest.mock import patch, MagicMock

from runpod_singleton.singleton import main, RunpodSingletonManager
from runpod_singleton import constants as const


@pytest.fixture
def mock_args() -> MagicMock:
    """Fixture for mocked parsed arguments."""
    args = MagicMock(spec=argparse.Namespace)
    args.config = MagicMock(spec=Path)
    args.api_key = "test_api_key"
    args.stop = False
    args.terminate = False
    args.debug = False
    return args


@patch("runpod_singleton.singleton.parse_args")
@patch("runpod_singleton.singleton.RunpodSingletonManager")
@patch("runpod_singleton.singleton.sys.exit")
def test_main_success(
    mock_exit: MagicMock,
    mock_manager_class: MagicMock,
    mock_parse_args: MagicMock,
    mock_args: MagicMock,
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
    mock_args: MagicMock,
):
    """Test main execution path when manager.run() returns False."""
    mock_parse_args.return_value = mock_args
    mock_manager_instance = MagicMock(spec=RunpodSingletonManager)
    mock_manager_instance.run.return_value = False
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
    mock_args: MagicMock,
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
    mock_args: MagicMock,
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
@patch("builtins.print") # Mock print to ensure it's NOT called
def test_main_system_exit_on_parse_args(
    mock_print: MagicMock,
    mock_exit: MagicMock,
    mock_manager_class: MagicMock,
    mock_parse_args: MagicMock,
):
    """Test main handles SystemExit raised by parse_args."""
    exit_code = 2
    parse_args_exception = SystemExit(exit_code)
    mock_parse_args.side_effect = parse_args_exception # Simulate argparse error

    main()

    mock_parse_args.assert_called_once()
    # Manager should NOT be initialized if parse_args fails
    mock_manager_class.assert_not_called()
    # print should NOT be called by our code (argparse handles its own error printing)
    mock_print.assert_not_called()
    # sys.exit should be called with the code from the SystemExit exception
    mock_exit.assert_called_once_with(exit_code)
