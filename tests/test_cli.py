"""CLI stories: every invocation a single beat."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterator

import pytest
from click.testing import CliRunner, Result

from lib_registry import __init__conf__
from lib_registry import cli as cli_mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TEST_KEY = "HKCU\\Software\\lib_registry_cli_test"


@pytest.fixture
def temp_key(cli_runner: CliRunner) -> Iterator[str]:
    """Create a temporary registry key, yield its path, delete on teardown."""
    cli_runner.invoke(cli_mod.cli, ["create-key", _TEST_KEY, "--parents"])
    yield _TEST_KEY
    cli_runner.invoke(cli_mod.cli, ["delete-key", _TEST_KEY, "--recursive", "--force"])


@pytest.fixture
def temp_file() -> Iterator[str]:
    """Yield a temporary file path, remove on teardown."""
    fp = os.path.join(tempfile.gettempdir(), "_lib_reg_cli_test.json")
    yield fp
    if os.path.isfile(fp):
        os.remove(fp)


# ---------------------------------------------------------------------------
# Scaffold tests
# ---------------------------------------------------------------------------


@pytest.mark.os_agnostic
def test_when_cli_runs_without_arguments_help_is_printed(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli_mod.cli, [])

    assert result.exit_code == 0
    assert "Usage:" in result.output


@pytest.mark.os_agnostic
def test_when_info_is_invoked_the_metadata_is_displayed(cli_runner: CliRunner) -> None:
    result: Result = cli_runner.invoke(cli_mod.cli, ["info"])

    assert result.exit_code == 0
    assert f"Info for {__init__conf__.name}:" in result.output
    assert __init__conf__.version in result.output


@pytest.mark.os_agnostic
def test_when_an_unknown_command_is_used_a_helpful_error_appears(cli_runner: CliRunner) -> None:
    result: Result = cli_runner.invoke(cli_mod.cli, ["does-not-exist"])

    assert result.exit_code != 0
    assert "No such command" in result.output


@pytest.mark.os_agnostic
def test_main_returns_zero_on_success() -> None:
    exit_code = cli_mod.main(["info"])
    assert exit_code == 0


@pytest.mark.os_agnostic
def test_version_option_displays_version(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli_mod.cli, ["--version"])

    assert result.exit_code == 0
    assert __init__conf__.version in result.output


@pytest.mark.os_agnostic
def test_main_catches_system_exit_and_returns_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_cli(**_kwargs: object) -> None:
        raise SystemExit(42)

    monkeypatch.setattr(cli_mod, "cli", fake_cli)
    exit_code = cli_mod.main(["info"])
    assert exit_code == 42


@pytest.mark.os_agnostic
def test_help_option_displays_help(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli_mod.cli, ["--help"])

    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "--traceback" in result.output
    assert "--quiet" in result.output
    assert "--json" in result.output


# ---------------------------------------------------------------------------
# get command
# ---------------------------------------------------------------------------


@pytest.mark.os_agnostic
def test_cli_get_reads_value(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(
        cli_mod.cli,
        [
            "get",
            "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion",
            "CurrentBuild",
        ],
    )
    assert result.exit_code == 0
    assert result.output.strip() != ""


@pytest.mark.os_agnostic
def test_cli_get_with_type_flag(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(
        cli_mod.cli,
        [
            "get",
            "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion",
            "CurrentBuild",
            "--type",
        ],
    )
    assert result.exit_code == 0
    assert "REG_" in result.output


@pytest.mark.os_agnostic
def test_cli_get_with_forward_slashes(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(
        cli_mod.cli,
        [
            "get",
            "HKLM/SOFTWARE/Microsoft/Windows NT/CurrentVersion",
            "CurrentBuild",
        ],
    )
    assert result.exit_code == 0
    assert result.output.strip() != ""


@pytest.mark.os_agnostic
def test_cli_get_json_output(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(
        cli_mod.cli,
        [
            "--json",
            "get",
            "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion",
            "CurrentBuild",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "data" in data
    assert "type" in data


@pytest.mark.os_agnostic
def test_cli_get_missing_value_fails(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(
        cli_mod.cli,
        [
            "get",
            "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion",
            "NoSuchValue_test",
        ],
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# exists command
# ---------------------------------------------------------------------------


@pytest.mark.os_agnostic
def test_cli_exists_returns_zero_for_existing_key(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(
        cli_mod.cli,
        [
            "exists",
            "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion",
        ],
    )
    assert result.exit_code == 0


@pytest.mark.os_agnostic
def test_cli_exists_returns_one_for_missing_key(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(
        cli_mod.cli,
        [
            "exists",
            "HKLM\\SOFTWARE\\DoesNotExist_lib_registry_test",
        ],
    )
    assert result.exit_code == 1


@pytest.mark.os_agnostic
def test_cli_exists_with_forward_slashes(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(
        cli_mod.cli,
        [
            "exists",
            "HKLM/SOFTWARE/Microsoft/Windows NT/CurrentVersion",
        ],
    )
    assert result.exit_code == 0


@pytest.mark.os_agnostic
def test_main_exists_returns_nonzero_for_missing_key() -> None:
    exit_code = cli_mod.main(["exists", "HKLM\\SOFTWARE\\DoesNotExist_lib_registry_test"])
    assert exit_code == 1


# ---------------------------------------------------------------------------
# list command
# ---------------------------------------------------------------------------


@pytest.mark.os_agnostic
def test_cli_list_shows_subkeys_and_values(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(
        cli_mod.cli,
        [
            "list",
            "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion",
        ],
    )
    assert result.exit_code == 0
    assert result.output.strip() != ""


@pytest.mark.os_agnostic
def test_cli_list_keys_only(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli_mod.cli, ["list", "--keys", "HKEY_USERS"])
    assert result.exit_code == 0
    assert "[KEY]" in result.output


@pytest.mark.os_agnostic
def test_cli_list_values_only(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(
        cli_mod.cli,
        [
            "list",
            "--values",
            "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion",
        ],
    )
    assert result.exit_code == 0
    assert "[KEY]" not in result.output


@pytest.mark.os_agnostic
def test_cli_list_recursive(cli_runner: CliRunner, temp_key: str) -> None:
    cli_runner.invoke(cli_mod.cli, ["create-key", f"{temp_key}\\child", "--parents"])
    result = cli_runner.invoke(cli_mod.cli, ["list", "--keys", "--recursive", temp_key])
    assert result.exit_code == 0
    assert "child" in result.output


@pytest.mark.os_agnostic
def test_cli_list_json(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli_mod.cli, ["--json", "list", "HKEY_USERS"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "subkeys" in data


# ---------------------------------------------------------------------------
# create-key / delete-key
# ---------------------------------------------------------------------------


@pytest.mark.os_agnostic
def test_cli_create_and_delete_key(cli_runner: CliRunner, temp_key: str) -> None:
    result = cli_runner.invoke(cli_mod.cli, ["exists", temp_key])
    assert result.exit_code == 0

    result = cli_runner.invoke(cli_mod.cli, ["delete-key", temp_key, "--recursive"])
    assert result.exit_code == 0

    result = cli_runner.invoke(cli_mod.cli, ["exists", temp_key])
    assert result.exit_code == 1

    # Re-create so fixture teardown doesn't fail
    cli_runner.invoke(cli_mod.cli, ["create-key", temp_key, "--parents"])


@pytest.mark.os_agnostic
def test_cli_delete_key_force_missing(cli_runner: CliRunner) -> None:
    """--force should suppress errors when key doesn't exist."""
    result = cli_runner.invoke(
        cli_mod.cli,
        [
            "delete-key",
            "HKCU\\Software\\does_not_exist_lib_reg_test",
            "--force",
        ],
    )
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# set / get / delete-value
# ---------------------------------------------------------------------------


@pytest.mark.os_agnostic
def test_cli_set_defaults_to_string(cli_runner: CliRunner, temp_key: str) -> None:
    cli_runner.invoke(cli_mod.cli, ["set", temp_key, "num_as_str", "42"])

    result = cli_runner.invoke(cli_mod.cli, ["get", "--type", temp_key, "num_as_str"])
    assert result.exit_code == 0
    assert "REG_SZ" in result.output
    assert "42" in result.output


@pytest.mark.os_agnostic
def test_cli_set_with_explicit_dword(cli_runner: CliRunner, temp_key: str) -> None:
    result = cli_runner.invoke(cli_mod.cli, ["set", temp_key, "count", "42", "--type", "REG_DWORD"])
    assert result.exit_code == 0

    result = cli_runner.invoke(cli_mod.cli, ["get", "--type", temp_key, "count"])
    assert "REG_DWORD" in result.output
    assert "42" in result.output


@pytest.mark.os_agnostic
def test_cli_set_dword_hex(cli_runner: CliRunner, temp_key: str) -> None:
    result = cli_runner.invoke(cli_mod.cli, ["set", temp_key, "hex_val", "0xFF", "--type", "REG_DWORD"])
    assert result.exit_code == 0

    result = cli_runner.invoke(cli_mod.cli, ["get", temp_key, "hex_val"])
    assert "255" in result.output


@pytest.mark.os_agnostic
def test_cli_set_dword_overflow_rejected(cli_runner: CliRunner, temp_key: str) -> None:
    result = cli_runner.invoke(cli_mod.cli, ["set", temp_key, "big", "5000000000", "--type", "REG_DWORD"])
    assert result.exit_code != 0


@pytest.mark.os_agnostic
def test_cli_set_dword_invalid_string_rejected(cli_runner: CliRunner, temp_key: str) -> None:
    result = cli_runner.invoke(cli_mod.cli, ["set", temp_key, "bad", "hello", "--type", "REG_DWORD"])
    assert result.exit_code != 0


@pytest.mark.os_agnostic
def test_cli_delete_value(cli_runner: CliRunner, temp_key: str) -> None:
    cli_runner.invoke(cli_mod.cli, ["set", temp_key, "to_delete", "bye"])

    result = cli_runner.invoke(cli_mod.cli, ["delete-value", temp_key, "to_delete"])
    assert result.exit_code == 0

    result = cli_runner.invoke(cli_mod.cli, ["get", temp_key, "to_delete"])
    assert result.exit_code != 0


@pytest.mark.os_agnostic
def test_cli_delete_value_missing_fails(cli_runner: CliRunner, temp_key: str) -> None:
    result = cli_runner.invoke(cli_mod.cli, ["delete-value", temp_key, "no_such_value_test"])
    assert result.exit_code != 0


@pytest.mark.os_agnostic
def test_cli_delete_value_force_missing(cli_runner: CliRunner, temp_key: str) -> None:
    result = cli_runner.invoke(cli_mod.cli, ["delete-value", temp_key, "no_such_value_test", "--force"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# export / import
# ---------------------------------------------------------------------------


@pytest.mark.os_agnostic
def test_cli_export_and_import(cli_runner: CliRunner, temp_key: str, temp_file: str) -> None:
    cli_runner.invoke(cli_mod.cli, ["set", temp_key, "color", "blue"])

    result = cli_runner.invoke(cli_mod.cli, ["export", temp_key, temp_file])
    assert result.exit_code == 0
    assert os.path.isfile(temp_file)

    import_target = "HKCU\\Software\\lib_registry_cli_test_imported"
    result = cli_runner.invoke(cli_mod.cli, ["import", "HKCU", "Software\\lib_registry_cli_test_imported", temp_file])
    assert result.exit_code == 0

    result = cli_runner.invoke(cli_mod.cli, ["exists", import_target])
    assert result.exit_code == 0

    cli_runner.invoke(cli_mod.cli, ["delete-key", import_target, "--recursive", "--force"])


@pytest.mark.os_agnostic
def test_cli_import_with_forward_slashes(cli_runner: CliRunner, temp_key: str, temp_file: str) -> None:
    cli_runner.invoke(cli_mod.cli, ["set", temp_key, "val", "test"])
    cli_runner.invoke(cli_mod.cli, ["export", temp_key, temp_file])

    import_target = "HKCU\\Software\\lib_registry_cli_test_fwd"
    result = cli_runner.invoke(cli_mod.cli, ["import", "HKCU", "Software/lib_registry_cli_test_fwd", temp_file])
    assert result.exit_code == 0

    result = cli_runner.invoke(cli_mod.cli, ["exists", import_target])
    assert result.exit_code == 0

    cli_runner.invoke(cli_mod.cli, ["delete-key", import_target, "--recursive", "--force"])


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


@pytest.mark.os_agnostic
def test_cli_search_finds_values(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(
        cli_mod.cli,
        [
            "search",
            "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion",
            "--name",
            "Current*",
        ],
    )
    assert result.exit_code == 0
    assert "Current" in result.output


@pytest.mark.os_agnostic
def test_cli_search_json(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(
        cli_mod.cli,
        [
            "--json",
            "search",
            "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion",
            "--name",
            "Current*",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) > 0


@pytest.mark.os_agnostic
def test_cli_search_missing_key_does_not_crash(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(
        cli_mod.cli,
        [
            "search",
            "HKLM\\SOFTWARE\\DoesNotExist_lib_registry_test",
            "--name",
            "*",
        ],
    )
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------


@pytest.mark.os_agnostic
def test_cli_users_lists_sids(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli_mod.cli, ["users"])
    assert result.exit_code == 0
    assert "S-1-5" in result.output


@pytest.mark.os_agnostic
def test_cli_users_json(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli_mod.cli, ["--json", "users"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert all("sid" in e and "username" in e for e in data)


# ---------------------------------------------------------------------------
# tree command
# ---------------------------------------------------------------------------


@pytest.mark.os_agnostic
def test_cli_tree_displays_hierarchy(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli_mod.cli, ["tree", "HKEY_USERS", "--depth", "1"])
    assert result.exit_code == 0
    assert "S-1-5" in result.output


@pytest.mark.os_agnostic
def test_cli_tree_json(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli_mod.cli, ["--json", "tree", "HKEY_USERS", "--depth", "1"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "name" in data


# ---------------------------------------------------------------------------
# copy command
# ---------------------------------------------------------------------------


@pytest.mark.os_agnostic
def test_cli_copy_values(cli_runner: CliRunner, temp_key: str) -> None:
    cli_runner.invoke(cli_mod.cli, ["set", temp_key, "color", "red"])

    dst = "HKCU\\Software\\lib_registry_cli_test_copy_dst"
    result = cli_runner.invoke(cli_mod.cli, ["copy", temp_key, dst])
    assert result.exit_code == 0

    result = cli_runner.invoke(cli_mod.cli, ["get", dst, "color"])
    assert result.exit_code == 0
    assert "red" in result.output

    cli_runner.invoke(cli_mod.cli, ["delete-key", dst, "--recursive", "--force"])


@pytest.mark.os_agnostic
def test_cli_copy_recursive(cli_runner: CliRunner, temp_key: str) -> None:
    child = f"{temp_key}\\sub"
    cli_runner.invoke(cli_mod.cli, ["create-key", child, "--parents"])
    cli_runner.invoke(cli_mod.cli, ["set", child, "val", "deep"])

    dst = "HKCU\\Software\\lib_registry_cli_test_copy_rec"
    result = cli_runner.invoke(cli_mod.cli, ["copy", temp_key, dst, "--recursive"])
    assert result.exit_code == 0

    result = cli_runner.invoke(cli_mod.cli, ["get", f"{dst}\\sub", "val"])
    assert result.exit_code == 0
    assert "deep" in result.output

    cli_runner.invoke(cli_mod.cli, ["delete-key", dst, "--recursive", "--force"])


# ---------------------------------------------------------------------------
# rename command
# ---------------------------------------------------------------------------


@pytest.mark.os_agnostic
def test_cli_rename_value(cli_runner: CliRunner, temp_key: str) -> None:
    cli_runner.invoke(cli_mod.cli, ["set", temp_key, "old_name", "data"])

    result = cli_runner.invoke(cli_mod.cli, ["rename", temp_key, "old_name", "new_name"])
    assert result.exit_code == 0

    result = cli_runner.invoke(cli_mod.cli, ["get", temp_key, "new_name"])
    assert result.exit_code == 0
    assert "data" in result.output

    result = cli_runner.invoke(cli_mod.cli, ["get", temp_key, "old_name"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# diff command
# ---------------------------------------------------------------------------


@pytest.mark.os_agnostic
def test_cli_diff_identical_keys(cli_runner: CliRunner, temp_key: str) -> None:
    cli_runner.invoke(cli_mod.cli, ["set", temp_key, "val", "same"])

    result = cli_runner.invoke(cli_mod.cli, ["diff", temp_key, temp_key])
    assert result.exit_code == 0
    assert "No differences" in result.output


@pytest.mark.os_agnostic
def test_cli_diff_different_keys(cli_runner: CliRunner, temp_key: str) -> None:
    cli_runner.invoke(cli_mod.cli, ["set", temp_key, "val", "aaa"])

    other = "HKCU\\Software\\lib_registry_cli_test_diff_other"
    cli_runner.invoke(cli_mod.cli, ["create-key", other, "--parents"])
    cli_runner.invoke(cli_mod.cli, ["set", other, "val", "bbb"])

    result = cli_runner.invoke(cli_mod.cli, ["diff", temp_key, other])
    assert result.exit_code == 0
    assert "~" in result.output or "differs" in result.output.lower()

    cli_runner.invoke(cli_mod.cli, ["delete-key", other, "--recursive", "--force"])


@pytest.mark.os_agnostic
def test_cli_diff_json(cli_runner: CliRunner, temp_key: str) -> None:
    cli_runner.invoke(cli_mod.cli, ["set", temp_key, "val", "x"])

    other = "HKCU\\Software\\lib_registry_cli_test_diff_json"
    cli_runner.invoke(cli_mod.cli, ["create-key", other, "--parents"])
    cli_runner.invoke(cli_mod.cli, ["set", other, "val", "y"])

    result = cli_runner.invoke(cli_mod.cli, ["--json", "diff", temp_key, other])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) > 0

    cli_runner.invoke(cli_mod.cli, ["delete-key", other, "--recursive", "--force"])


# ---------------------------------------------------------------------------
# quiet flag
# ---------------------------------------------------------------------------


@pytest.mark.os_agnostic
def test_cli_quiet_suppresses_output(cli_runner: CliRunner, temp_key: str) -> None:
    cli_runner.invoke(cli_mod.cli, ["set", temp_key, "val", "data"])

    dst = "HKCU\\Software\\lib_registry_cli_test_quiet"
    result = cli_runner.invoke(cli_mod.cli, ["-q", "copy", temp_key, dst])
    assert result.exit_code == 0
    assert result.output.strip() == ""

    cli_runner.invoke(cli_mod.cli, ["delete-key", dst, "--recursive", "--force"])
