"""Shared pytest fixtures for CLI and module-entry tests."""

from __future__ import annotations

import re
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
