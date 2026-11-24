"""Recursive CLI walks release their key handles; the registry API returns named records."""

import json
import uuid
from collections.abc import Callable, Iterator

import pytest
from click.testing import CliRunner

import lib_registry
from lib_registry import KeyInfo, Registry, RegValue, ResolvedKey, TypedValue, resolve_key, winreg
from lib_registry import _cli_helpers as helpers


@pytest.fixture
def tree_key() -> Iterator[str]:
    """Create a three-level subtree with values, private to this test, and delete it afterwards."""
    key = f"HKCU\\Software\\lib_registry_walk_test_{uuid.uuid4().hex}"
    with Registry() as registry:
        for child in ("a", "b", "c"):
            registry.create_key(f"{key}\\{child}\\leaf", parents=True)
            registry.set_value(f"{key}\\{child}", "name", child)
            registry.set_value(f"{key}\\{child}\\leaf", "number", 7)
    yield key
    with Registry() as registry:
        registry.delete_key(key, delete_subkeys=True, missing_ok=True)


def _handles_below(registry: Registry, key: str) -> list[tuple[int, str, int]]:
    """Return the cached handles of the keys strictly below ``key``."""
    hive_key, sub_key = resolve_key(key)
    return [cache_key for cache_key in registry.reg_key_handles if cache_key[0] == hive_key and cache_key[1].startswith(sub_key + "\\")]


_WALKS: dict[str, Callable[[Registry, str], object]] = {
    "search": lambda registry, key: list(helpers.search_recursive(registry, key, "*", None)),
    "diff": lambda registry, key: list(helpers.diff_keys(registry, key, f"{key}\\a")),
    "list": lambda registry, key: helpers.list_to_dict(registry, key, show_keys=True, show_values=True, recursive=True),
    "tree": lambda registry, key: helpers.tree_to_dict(registry, key, 10),
}


@pytest.mark.os_agnostic
@pytest.mark.parametrize("walk", sorted(_WALKS))
def test_a_recursive_walk_leaves_no_handle_open_below_the_walked_key(tree_key: str, walk: str) -> None:
    with Registry() as registry:
        _WALKS[walk](registry, tree_key)

        assert _handles_below(registry, tree_key) == []


@pytest.mark.os_agnostic
def test_a_recursive_copy_leaves_no_handle_open_below_either_key(tree_key: str) -> None:
    destination = f"{tree_key}_copy"
    with Registry() as registry:
        registry.create_key(destination)
        helpers.copy_recursive(registry, tree_key, destination)

        assert _handles_below(registry, tree_key) == []
        assert _handles_below(registry, destination) == []
        assert registry.get_value(f"{destination}\\b\\leaf", "number") == 7
        registry.delete_key(destination, delete_subkeys=True)


@pytest.mark.os_agnostic
def test_a_walk_keeps_a_handle_the_caller_had_open(tree_key: str) -> None:
    with Registry() as registry:
        handle = registry._open_key(f"{tree_key}\\b")  # pyright: ignore[reportPrivateUsage] - the cache the walk must not empty

        list(helpers.search_recursive(registry, tree_key, "*", None))

        assert list(registry.reg_key_handles.values()) == [handle]


@pytest.mark.os_agnostic
def test_delete_key_with_delete_subkeys_removes_every_child(tree_key: str) -> None:
    with Registry() as registry:
        registry.delete_key(tree_key, delete_subkeys=True)

        assert not registry.key_exist(tree_key)


@pytest.mark.os_agnostic
def test_the_registry_api_returns_named_records(tree_key: str) -> None:
    with Registry() as registry:
        info = registry.key_info(tree_key)
        typed = registry.get_value_ex(f"{tree_key}\\a\\leaf", "number")
        values = list(registry.values(f"{tree_key}\\a"))

    assert type(info) is KeyInfo
    assert (info.number_of_subkeys, info.number_of_values) == (3, 0)
    assert type(typed) is TypedValue
    assert (typed.data, typed.reg_type) == (7, winreg.REG_DWORD)
    assert [type(value) for value in values] == [RegValue]
    assert (values[0].name, values[0].data, values[0].reg_type) == ("name", "a", winreg.REG_SZ)
    assert type(resolve_key(tree_key)) is ResolvedKey


@pytest.mark.os_agnostic
@pytest.mark.parametrize("count", [0, 1, 3])
def test_echo_json_array_prints_what_json_dumps_prints(count: int) -> None:
    items: list[dict[str, object]] = [{"key": f"k{i}", "nested": {"list": [i, "x\ny"]}} for i in range(count)]

    @helpers.click.command()
    def emit() -> None:
        helpers.echo_json_array(iter(items))

    result = CliRunner().invoke(emit)

    assert result.output == json.dumps(items, indent=2) + "\n"


@pytest.mark.os_agnostic
def test_a_value_diff_refuses_a_subkey_kind() -> None:
    with pytest.raises(ValueError, match="SUBKEY_ONLY_IN_A"):
        helpers.ValueOnlyIn(helpers.DiffKind.SUBKEY_ONLY_IN_A, "HKCU\\A", "v", "x")


@pytest.mark.os_agnostic
def test_a_subkey_diff_refuses_a_value_kind() -> None:
    with pytest.raises(ValueError, match="ONLY_IN_B"):
        helpers.SubkeyOnlyIn(helpers.DiffKind.ONLY_IN_B, "HKCU\\A\\k")


@pytest.mark.os_agnostic
def test_diff_kinds_keep_their_wire_values() -> None:
    assert [kind.value for kind in helpers.DiffKind] == ["only_in_a", "only_in_b", "value_differs", "subkey_only_in_a", "subkey_only_in_b"]
    assert json.dumps(helpers.DiffKind.ONLY_IN_A) == '"only_in_a"'


@pytest.mark.os_agnostic
@pytest.mark.parametrize("name", ["main_key_hashed_by_name", "hive_names_hashed_by_int", "reg_type_names_hashed_by_int"])
def test_the_exported_lookup_tables_refuse_writes(name: str) -> None:
    table = getattr(lib_registry, name)
    key = next(iter(table))

    # A read-only mapping has no item assignment, so Python falls back to the sequence protocol:
    # that raises TypeError, or IndexError first when the key is an HKEY constant too large to be
    # an index. Either way nothing is written.
    with pytest.raises((TypeError, IndexError)):
        table[key] = table[key]
    assert not hasattr(table, "__setitem__")
    assert dict(table)[key] == table[key]
