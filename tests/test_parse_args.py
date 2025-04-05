import pytest
import sys
from pathlib import Path
from unittest.mock import patch

# Import the function to test
from runpod_singleton.singleton import parse_args


def test_parse_args_required_only():
    """Test parsing with only the required config argument."""
    config_file = "config.yaml"
    with patch.object(sys, "argv", ["script_name", config_file]):
        args = parse_args()
        assert isinstance(args.config, Path)
        assert args.config == Path(config_file)
        assert args.api_key is None
        assert args.stop is False
        assert args.terminate is False
        assert args.debug is False


def test_parse_args_api_key():
    """Test parsing with the --api-key argument."""
    config_file = "config.yaml"
    api_key_value = "my_secret_key"
    with patch.object(sys, "argv", ["script_name", config_file, "--api-key", api_key_value]):
        args = parse_args()
        assert args.config == Path(config_file)
        assert args.api_key == api_key_value
        assert args.stop is False
        assert args.terminate is False
        assert args.debug is False


def test_parse_args_stop():
    """Test parsing with the --stop flag."""
    config_file = "config.yaml"
    with patch.object(sys, "argv", ["script_name", config_file, "--stop"]):
        args = parse_args()
        assert args.config == Path(config_file)
        assert args.api_key is None
        assert args.stop is True
        assert args.terminate is False
        assert args.debug is False


def test_parse_args_terminate():
    """Test parsing with the --terminate flag."""
    config_file = "config.yaml"
    with patch.object(sys, "argv", ["script_name", config_file, "--terminate"]):
        args = parse_args()
        assert args.config == Path(config_file)
        assert args.api_key is None
        assert args.stop is False
        assert args.terminate is True
        assert args.debug is False


def test_parse_args_debug():
    """Test parsing with the --debug flag."""
    config_file = "config.yaml"
    with patch.object(sys, "argv", ["script_name", config_file, "--debug"]):
        args = parse_args()
        assert args.config == Path(config_file)
        assert args.api_key is None
        assert args.stop is False
        assert args.terminate is False
        assert args.debug is True


def test_parse_args_all_flags():
    """Test parsing with a combination of optional arguments."""
    config_file = "my/path/to/config.yaml"
    api_key_value = "another_key"
    with patch.object(
        sys,
        "argv",
        [
            "script_name",
            config_file,
            "--api-key",
            api_key_value,
            "--stop",
            "--debug",
            "--terminate", # Order shouldn't matter
        ],
    ):
        args = parse_args()
        assert args.config == Path(config_file)
        assert args.api_key == api_key_value
        assert args.stop is True
        assert args.terminate is True
        assert args.debug is True


def test_parse_args_missing_config():
    """Test that argparse exits when the required config argument is missing."""
    with patch.object(sys, "argv", ["script_name", "--debug"]):
        # Argparse raises SystemExit by default on error
        with pytest.raises(SystemExit):
            parse_args()
