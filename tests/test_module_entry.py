"""Module entry stories ensuring `python -m` mirrors the CLI."""

import runpy
import sys

import pytest

from lib_registry import cli as cli_mod


@pytest.mark.os_agnostic
def test_when_module_entry_returns_zero_the_story_matches_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """Module entry should successfully execute info command."""
    monkeypatch.setattr(sys, "argv", ["lib_registry", "info"], raising=False)

    with pytest.raises(SystemExit) as exc:
        runpy.run_module("lib_registry.__main__", run_name="__main__")

    assert exc.value.code == 0


@pytest.mark.os_agnostic
def test_when_module_entry_imports_cli_the_alias_stays_intact() -> None:
    """CLI name should be accessible."""
    assert hasattr(cli_mod.cli, "name")
