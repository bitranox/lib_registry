"""Shared pytest fixtures for CLI and module-entry tests."""

import re
import sys
from collections.abc import Callable

import pytest
from click.testing import CliRunner

ANSI_ESCAPE_PATTERN = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def _remove_ansi_codes(text: str) -> str:
    """Return text stripped of ANSI escape sequences.

    Tests compare human-readable CLI output; stripping colour codes keeps
    assertions stable across environments.

    Args:
        text: Raw string captured from CLI output.

    Returns:
        The string without ANSI escape sequences.

    """
    return ANSI_ESCAPE_PATTERN.sub("", text)


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a fresh CliRunner per test."""
    return CliRunner()


@pytest.fixture
def strip_ansi() -> Callable[[str], str]:
    """Return a helper that strips ANSI escape sequences from a string."""
    return _remove_ansi_codes


#: Which platforms each ``os_*`` marker lets a test run on. Registering a marker in pyproject only
#: silences pytest's unknown-marker warning; without this table a marked test runs everywhere.
_PLATFORM_MARKERS: dict[str, Callable[[str], bool]] = {
    "os_windows": lambda platform: platform == "win32",
    "os_macos": lambda platform: platform == "darwin",
    "os_linux": lambda platform: platform.startswith("linux"),
    "os_posix": lambda platform: platform != "win32",
}


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Skip a test whose ``os_*`` marker names a platform other than the running one."""
    for name, runs_on in _PLATFORM_MARKERS.items():
        if item.get_closest_marker(name) is not None and not runs_on(sys.platform):
            pytest.skip(f"marked {name}; this is {sys.platform}")
