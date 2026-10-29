"""CLI stories: every invocation a single beat."""

import json
import sys
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from lib_registry import __init__conf__
from lib_registry import cli as cli_mod

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_KEY_PREFIX = "HKCU\\Software\\lib_registry_cli_test"


@pytest.fixture
def temp_key(cli_runner: CliRunner) -> Iterator[str]:
    """Create a registry key private to this test, yield its path, delete it on teardown.

    The name is unique per test rather than fixed: on Windows every test writes the one real HKCU, and
    pytest-xdist workers, like the parallel pytest per Python version of ``bmk test-all``, run tests
    at the same time. With one shared key a test's teardown deleted the key another test was still
    writing to. The same reasoning as ``temp_file`` below.
    """
    key = f"{_KEY_PREFIX}_{uuid.uuid4().hex}"
    cli_runner.invoke(cli_mod.cli, ["create-key", key, "--parents"])
    yield key
    cli_runner.invoke(cli_mod.cli, ["delete-key", key, "--recursive", "--force"])


@pytest.fixture
def key_beside(cli_runner: CliRunner, temp_key: str) -> Iterator[Callable[[str], str]]:
    """Return a factory naming a second key next to ``temp_key``; every named key is deleted on teardown.

    For a test that needs a target outside its own key (a copy or diff partner, an import target).
    Deriving it from ``temp_key`` keeps it private to the test, and deleting it here rather than at
    the end of the test body cleans it up when an assertion fails first.
    """
    named: list[str] = []

    def name(suffix: str) -> str:
        key = f"{temp_key}_{suffix}"
        named.append(key)
        return key

    yield name
    for key in named:
        cli_runner.invoke(cli_mod.cli, ["delete-key", key, "--recursive", "--force"])


@pytest.fixture
def temp_file(tmp_path: Path) -> str:
    """Return an export file path private to this test.

    Built under ``tmp_path`` rather than a fixed name in the system temp dir: ``bmk test-all`` runs
    one pytest per Python version in parallel, and a shared path let the cells overwrite or delete
    each other's export mid-test. pytest removes ``tmp_path`` itself, so no teardown is needed.
    """
    return str(tmp_path / "export.json")


@pytest.mark.os_agnostic
def test_each_test_writes_a_registry_key_of_its_own(cli_runner: CliRunner, temp_key: str) -> None:
    # A shared fixed key let one test's teardown delete what a parallel test was writing.
    suffix = temp_key.removeprefix(f"{_KEY_PREFIX}_")
    assert suffix != temp_key
    assert len(suffix) == 32
    assert all(c in "0123456789abcdef" for c in suffix)
    assert cli_runner.invoke(cli_mod.cli, ["exists", temp_key]).exit_code == 0


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


@pytest.mark.skipif(sys.platform == "win32", reason="SaveKey/LoadKey requires admin on Windows")
def test_cli_export_and_import(cli_runner: CliRunner, temp_key: str, temp_file: str, key_beside: Callable[[str], str]) -> None:
    cli_runner.invoke(cli_mod.cli, ["set", temp_key, "color", "blue"])

    result = cli_runner.invoke(cli_mod.cli, ["export", temp_key, temp_file])
    assert result.exit_code == 0
    assert Path(temp_file).is_file()

    import_target = key_beside("imported")
    subkey = import_target.removeprefix("HKCU\\")
    result = cli_runner.invoke(cli_mod.cli, ["import", "HKCU", subkey, temp_file])
    assert result.exit_code == 0

    result = cli_runner.invoke(cli_mod.cli, ["exists", import_target])
    assert result.exit_code == 0


@pytest.mark.skipif(sys.platform == "win32", reason="SaveKey/LoadKey requires admin on Windows")
def test_cli_import_with_forward_slashes(cli_runner: CliRunner, temp_key: str, temp_file: str, key_beside: Callable[[str], str]) -> None:
    cli_runner.invoke(cli_mod.cli, ["set", temp_key, "val", "test"])
    cli_runner.invoke(cli_mod.cli, ["export", temp_key, temp_file])

    import_target = key_beside("fwd")
    subkey = import_target.removeprefix("HKCU\\").replace("\\", "/")
    result = cli_runner.invoke(cli_mod.cli, ["import", "HKCU", subkey, temp_file])
    assert result.exit_code == 0

    result = cli_runner.invoke(cli_mod.cli, ["exists", import_target])
    assert result.exit_code == 0


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
# sid / whoami commands
# ---------------------------------------------------------------------------


@pytest.mark.os_agnostic
def test_cli_sid_resolves_default(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli_mod.cli, ["sid", ".DEFAULT"])
    assert result.exit_code == 0
    assert "Default" in result.output


@pytest.mark.os_agnostic
def test_cli_sid_json(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli_mod.cli, ["--json", "sid", ".DEFAULT"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["username"] == "Default"


@pytest.mark.os_agnostic
def test_cli_whoami_resolves_username(cli_runner: CliRunner) -> None:
    """Resolve the first real user's SID back from their username."""
    registry = cli_mod.Registry()
    sids = list(registry.sids())
    first_user = registry.username_from_sid(sids[0])

    result = cli_runner.invoke(cli_mod.cli, ["whoami", first_user])
    assert result.exit_code == 0
    assert sids[0] in result.output


@pytest.mark.os_agnostic
def test_cli_whoami_json(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli_mod.cli, ["--json", "whoami", "Default"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["sid"] == ".DEFAULT"


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
def test_cli_copy_values(cli_runner: CliRunner, temp_key: str, key_beside: Callable[[str], str]) -> None:
    cli_runner.invoke(cli_mod.cli, ["set", temp_key, "color", "red"])

    dst = key_beside("copy_dst")
    result = cli_runner.invoke(cli_mod.cli, ["copy", temp_key, dst])
    assert result.exit_code == 0

    result = cli_runner.invoke(cli_mod.cli, ["get", dst, "color"])
    assert result.exit_code == 0
    assert "red" in result.output


@pytest.mark.os_agnostic
def test_cli_copy_recursive(cli_runner: CliRunner, temp_key: str, key_beside: Callable[[str], str]) -> None:
    child = f"{temp_key}\\sub"
    cli_runner.invoke(cli_mod.cli, ["create-key", child, "--parents"])
    cli_runner.invoke(cli_mod.cli, ["set", child, "val", "deep"])

    dst = key_beside("copy_rec")
    result = cli_runner.invoke(cli_mod.cli, ["copy", temp_key, dst, "--recursive"])
    assert result.exit_code == 0

    result = cli_runner.invoke(cli_mod.cli, ["get", f"{dst}\\sub", "val"])
    assert result.exit_code == 0
    assert "deep" in result.output


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
def test_cli_diff_different_keys(cli_runner: CliRunner, temp_key: str, key_beside: Callable[[str], str]) -> None:
    cli_runner.invoke(cli_mod.cli, ["set", temp_key, "val", "aaa"])

    other = key_beside("diff_other")
    cli_runner.invoke(cli_mod.cli, ["create-key", other, "--parents"])
    cli_runner.invoke(cli_mod.cli, ["set", other, "val", "bbb"])

    result = cli_runner.invoke(cli_mod.cli, ["diff", temp_key, other])
    assert result.exit_code == 0
    assert "~" in result.output or "differs" in result.output.lower()


@pytest.mark.os_agnostic
def test_cli_diff_json(cli_runner: CliRunner, temp_key: str, key_beside: Callable[[str], str]) -> None:
    cli_runner.invoke(cli_mod.cli, ["set", temp_key, "val", "x"])

    other = key_beside("diff_json")
    cli_runner.invoke(cli_mod.cli, ["create-key", other, "--parents"])
    cli_runner.invoke(cli_mod.cli, ["set", other, "val", "y"])

    result = cli_runner.invoke(cli_mod.cli, ["--json", "diff", temp_key, other])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) > 0


# ---------------------------------------------------------------------------
# quiet flag
# ---------------------------------------------------------------------------


@pytest.mark.os_agnostic
def test_cli_quiet_suppresses_output(cli_runner: CliRunner, temp_key: str, key_beside: Callable[[str], str]) -> None:
    cli_runner.invoke(cli_mod.cli, ["set", temp_key, "val", "data"])

    dst = key_beside("quiet")
    result = cli_runner.invoke(cli_mod.cli, ["-q", "copy", temp_key, dst])
    assert result.exit_code == 0
    assert result.output.strip() == ""
