"""Shared pytest fixtures for CLI and module-entry tests."""

import re
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner

import lib_registry.registry

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


#: The doctests in ``lib_registry/registry.py`` share one registry per process (``fake_winreg``
#: off Windows, the real HKCU on Windows) and build on each other in file order: ``create_key`` creates
#: ``HKCU\Software`` that the reflection examples open later, and several create and delete the
#: same ``HKCU\Software\lib_registry_test`` key. Spread over pytest-xdist workers, an example
#: lands in a registry its predecessor never touched, so they run as one group on one worker.
_REGISTRY_MODULE = Path(lib_registry.registry.__file__).resolve()


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Put every doctest of ``lib_registry/registry.py`` into one ``xdist_group``.

    ``tryfirst`` is required: pytest-xdist turns the mark into the ``@<group>`` nodeid suffix in its
    own ``pytest_collection_modifyitems``, so a mark added after that hook groups nothing.
    """
    for item in items:
        if item.path.resolve() == _REGISTRY_MODULE:
            item.add_marker(pytest.mark.xdist_group("registry-doctests"))
