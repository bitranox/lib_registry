"""Helper functions for CLI commands - parsing, formatting, tree/diff operations.

The recursive walkers release the key handles they open once they leave a key
(see ``released_handles``), so a walk over a large subtree holds one handle per
level of depth instead of one per visited key. Search and diff yield their
results one at a time, and ``echo_json_array`` prints them as they come.
"""

import contextlib
import fnmatch
import json
import textwrap
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import NamedTuple

import rich_click as click
from rich.tree import Tree

from ._helpers import get_value_type_as_string, resolve_key
from ._winreg_setup import RegData, reg_type_names_hashed_by_int, winreg
from .exceptions import RegistryKeyNotFoundError
from .records import RegValue
from .registry import Registry

_TYPE_NAMES = list(reg_type_names_hashed_by_int.values())
_TYPE_NAME_TO_INT: Mapping[str, int] = MappingProxyType({v: k for k, v in reg_type_names_hashed_by_int.items()})
#: Largest value a REG_DWORD (unsigned 32-bit integer) can hold.
_REG_DWORD_MAX = 0xFFFFFFFF


def json_safe(obj: object) -> object:
    """Make non-serializable objects JSON-safe."""
    if isinstance(obj, bytes):
        return obj.hex()
    return str(obj)


class ParsedValue(NamedTuple):
    """CLI data converted for ``Registry.set_value``; ``reg_type`` None means infer it."""

    data: RegData
    reg_type: int | None


def parse_value_and_type(data: str, type_name: str | None) -> ParsedValue:
    """Convert CLI string data to the appropriate Python type.

    Without ``--type``, data is always stored as REG_SZ (string).
    Use ``--type REG_DWORD`` explicitly for integers.

    Examples:
        >>> parse_value_and_type("0x10", "REG_DWORD")
        ParsedValue(data=16, reg_type=4)
        >>> parse_value_and_type("text", None)
        ParsedValue(data='text', reg_type=None)
    """
    if type_name is None:
        return ParsedValue(data, None)

    reg_type = _TYPE_NAME_TO_INT[type_name.upper()]

    if reg_type in (winreg.REG_DWORD, winreg.REG_QWORD):
        try:
            value = int(data, 0)
        except ValueError:
            raise click.BadParameter(f'"{data}" is not a valid integer for {type_name}') from None
        if reg_type == winreg.REG_DWORD and not (0 <= value <= _REG_DWORD_MAX):
            raise click.BadParameter(f'"{data}" overflows REG_DWORD (0..4294967295)') from None
        return ParsedValue(value, reg_type)
    if reg_type == winreg.REG_BINARY:
        return ParsedValue(data.encode("utf-8"), reg_type)
    if reg_type == winreg.REG_MULTI_SZ:
        return ParsedValue(data.split("\\0"), reg_type)
    if reg_type == winreg.REG_NONE:
        return ParsedValue(None, reg_type)
    return ParsedValue(data, reg_type)


def value_to_json(value: RegValue) -> dict[str, object]:
    """Render one registry value in the CLI's JSON form (``name``, ``data``, ``type``).

    Examples:
        >>> value_to_json(RegValue("n", b"\\x00\\xff", winreg.REG_BINARY))
        {'name': 'n', 'data': '00ff', 'type': 'REG_BINARY'}
    """
    return {"name": value.name, "data": json_safe(value.data), "type": get_value_type_as_string(value.reg_type)}


def echo_json_array(items: Iterable[Mapping[str, object]]) -> None:
    """Print ``items`` as one JSON array while they are produced.

    The output is byte-identical to ``json.dumps(list(items), indent=2)``, but
    only one item is held at a time.

    Examples:
        >>> echo_json_array([{"a": 1}, {"b": [2]}])
        [
          {
            "a": 1
          },
          {
            "b": [
              2
            ]
          }
        ]
        >>> echo_json_array([])
        []
    """
    opened = False
    for item in items:
        click.echo(",\n" if opened else "[\n", nl=False)
        opened = True
        click.echo(textwrap.indent(json.dumps(item, indent=2), "  "), nl=False)
    click.echo("\n]" if opened else "[]")


@contextlib.contextmanager
def released_handles(registry: Registry, key: str) -> Iterator[None]:
    """Close the handles opened for ``key`` inside the block once the block ends.

    ``Registry`` caches every handle it opens until ``close_all``, so a walk
    over a subtree would otherwise keep one open handle per visited key.
    Handles that were already open when the block started stay open: they
    belong to the caller.
    """
    hive_key, sub_key = resolve_key(key)
    cache_keys = [(hive_key, sub_key, access) for access in (winreg.KEY_READ, winreg.KEY_ALL_ACCESS)]
    opened_by_caller = {cache_key for cache_key in cache_keys if cache_key in registry.reg_key_handles}
    try:
        yield
    finally:
        for cache_key in cache_keys:
            if cache_key in opened_by_caller:
                continue
            handle = registry.reg_key_handles.pop(cache_key, None)
            if handle is not None:
                handle.Close()


def list_human(registry: Registry, key: str, *, show_keys: bool, show_values: bool, recursive: bool, indent: int) -> None:
    """Print key contents in human-readable format."""
    prefix = "  " * indent
    with released_handles(registry, key):
        if show_keys:
            for subkey in registry.subkeys(key):
                click.echo(f"{prefix}[KEY] {subkey}")
                if recursive:
                    list_human(
                        registry,
                        f"{key}\\{subkey}",
                        show_keys=show_keys,
                        show_values=show_values,
                        recursive=recursive,
                        indent=indent + 1,
                    )
        if show_values:
            for value in registry.values(key):
                click.echo(f"{prefix}[{get_value_type_as_string(value.reg_type)}] {value.name} = {value.data}")


def list_to_dict(registry: Registry, key: str, *, show_keys: bool, show_values: bool, recursive: bool) -> dict[str, object]:
    """Build the JSON document for ``list``: the key, its subkeys and its values."""
    result: dict[str, object] = {"key": key}
    with released_handles(registry, key):
        if show_keys:
            subkeys: list[object] = []
            for subkey in registry.subkeys(key):
                if recursive:
                    subkeys.append(list_to_dict(registry, f"{key}\\{subkey}", show_keys=show_keys, show_values=show_values, recursive=recursive))
                else:
                    subkeys.append(subkey)
            result["subkeys"] = subkeys
        if show_values:
            result["values"] = [value_to_json(value) for value in registry.values(key)]
    return result


@dataclass(frozen=True)
class SearchHit:
    """A value that matched ``search``, with the key holding it."""

    key: str
    value: RegValue

    def to_json(self) -> dict[str, object]:
        """Return the hit in the CLI's JSON form (``key``, ``name``, ``data``, ``type``)."""
        return {"key": self.key, **value_to_json(self.value)}


def search_recursive(registry: Registry, key: str, name_pattern: str | None, data_pattern: str | None) -> Iterator[SearchHit]:
    """Yield the values under ``key`` whose name and data match the glob patterns.

    A key that vanishes during the walk ends the search below it, not the whole search.
    """
    with released_handles(registry, key):
        try:
            for value in registry.values(key):
                if name_pattern and not fnmatch.fnmatch(value.name, name_pattern):
                    continue
                if data_pattern and not fnmatch.fnmatch(str(value.data), data_pattern):
                    continue
                yield SearchHit(key, value)
        except RegistryKeyNotFoundError:
            return

        try:
            for subkey in registry.subkeys(key):
                yield from search_recursive(registry, f"{key}\\{subkey}", name_pattern, data_pattern)
        except RegistryKeyNotFoundError:
            return


def echo_search_hit(hit: SearchHit) -> None:
    """Print one search hit in the human-readable form."""
    click.echo(f"{hit.key}  [{get_value_type_as_string(hit.value.reg_type)}] {hit.value.name} = {hit.value.data}")


def build_tree(registry: Registry, key: str, tree: Tree, max_depth: int, current_depth: int = 0) -> None:
    """Recursively build a Rich Tree for display."""
    if current_depth >= max_depth:
        return
    with released_handles(registry, key), contextlib.suppress(RegistryKeyNotFoundError):
        for subkey in registry.subkeys(key):
            branch = tree.add(f"[bold]{subkey}[/bold]")
            build_tree(registry, f"{key}\\{subkey}", branch, max_depth, current_depth + 1)


def tree_to_dict(registry: Registry, key: str, max_depth: int, current_depth: int = 0) -> dict[str, object]:
    """Build a dict tree for JSON output."""
    result: dict[str, object] = {"name": key.rsplit("\\", 1)[-1] if "\\" in key else key}
    if current_depth >= max_depth:
        return result
    children: list[dict[str, object]] = []
    with released_handles(registry, key), contextlib.suppress(RegistryKeyNotFoundError):
        children.extend(tree_to_dict(registry, f"{key}\\{subkey}", max_depth, current_depth + 1) for subkey in registry.subkeys(key))
    if children:
        result["children"] = children
    return result


def copy_values(registry: Registry, src_key: str, dst_key: str) -> None:
    """Copy all values from src_key to dst_key."""
    for value in registry.values(src_key):
        registry.set_value(dst_key, value.name, value.data, value.reg_type)


def copy_recursive(registry: Registry, src_key: str, dst_key: str) -> None:
    """Recursively copy subkeys and values."""
    for subkey in registry.subkeys(src_key):
        src_child = f"{src_key}\\{subkey}"
        dst_child = f"{dst_key}\\{subkey}"
        with released_handles(registry, src_child), released_handles(registry, dst_child):
            registry.create_key(dst_child, parents=True)
            copy_values(registry, src_child, dst_child)
            copy_recursive(registry, src_child, dst_child)


class DiffKind(str, Enum):
    """What one difference found by ``diff`` is; the value is its JSON ``kind``.

    A ``str`` mixin rather than ``StrEnum`` for the Python 3.10 floor: ``json``
    writes the value, and nothing formats a member into a string.
    """

    ONLY_IN_A = "only_in_a"
    ONLY_IN_B = "only_in_b"
    VALUE_DIFFERS = "value_differs"
    SUBKEY_ONLY_IN_A = "subkey_only_in_a"
    SUBKEY_ONLY_IN_B = "subkey_only_in_b"


@dataclass(frozen=True)
class ValueOnlyIn:
    """A value present in only one of the two keys (``kind`` ONLY_IN_A or ONLY_IN_B)."""

    kind: DiffKind
    path: str
    name: str
    data: RegData

    def __post_init__(self) -> None:
        if self.kind not in (DiffKind.ONLY_IN_A, DiffKind.ONLY_IN_B):
            raise ValueError(f"ValueOnlyIn takes ONLY_IN_A or ONLY_IN_B, not {self.kind.name}")

    def to_json(self) -> dict[str, object]:
        """Return the difference in the CLI's JSON form."""
        return {"kind": self.kind, "path": self.path, "name": self.name, "value": json_safe(self.data)}


@dataclass(frozen=True)
class ValueDiffers:
    """A value present in both keys with different data or type."""

    path: str
    name: str
    data_a: RegData
    data_b: RegData

    def to_json(self) -> dict[str, object]:
        """Return the difference in the CLI's JSON form."""
        return {
            "kind": DiffKind.VALUE_DIFFERS,
            "path": self.path,
            "name": self.name,
            "value_a": json_safe(self.data_a),
            "value_b": json_safe(self.data_b),
        }


@dataclass(frozen=True)
class SubkeyOnlyIn:
    """A subkey present below only one of the two keys (``kind`` SUBKEY_ONLY_IN_A or _B)."""

    kind: DiffKind
    path: str

    def __post_init__(self) -> None:
        if self.kind not in (DiffKind.SUBKEY_ONLY_IN_A, DiffKind.SUBKEY_ONLY_IN_B):
            raise ValueError(f"SubkeyOnlyIn takes SUBKEY_ONLY_IN_A or SUBKEY_ONLY_IN_B, not {self.kind.name}")

    def to_json(self) -> dict[str, object]:
        """Return the difference in the CLI's JSON form."""
        return {"kind": self.kind, "path": self.path}


KeyDiff = ValueOnlyIn | ValueDiffers | SubkeyOnlyIn


def diff_keys(registry: Registry, key_a: str, key_b: str) -> Iterator[KeyDiff]:
    """Yield the differences between two registry key subtrees, values before subkeys."""
    with released_handles(registry, key_a), released_handles(registry, key_b):
        vals_a = {value.name: value for value in registry.values(key_a)}
        vals_b = {value.name: value for value in registry.values(key_b)}

        for name in sorted(vals_a.keys() | vals_b.keys()):
            value_a, value_b = vals_a.get(name), vals_b.get(name)
            if value_b is None and value_a is not None:
                yield ValueOnlyIn(DiffKind.ONLY_IN_A, key_a, name, value_a.data)
            elif value_a is None and value_b is not None:
                yield ValueOnlyIn(DiffKind.ONLY_IN_B, key_b, name, value_b.data)
            elif value_a is not None and value_b is not None and (value_a.data, value_a.reg_type) != (value_b.data, value_b.reg_type):
                yield ValueDiffers(key_a, name, value_a.data, value_b.data)

        subs_a = set(registry.subkeys(key_a))
        subs_b = set(registry.subkeys(key_b))

    for subkey in sorted(subs_a - subs_b):
        yield SubkeyOnlyIn(DiffKind.SUBKEY_ONLY_IN_A, f"{key_a}\\{subkey}")
    for subkey in sorted(subs_b - subs_a):
        yield SubkeyOnlyIn(DiffKind.SUBKEY_ONLY_IN_B, f"{key_b}\\{subkey}")
    for subkey in sorted(subs_a & subs_b):
        yield from diff_keys(registry, f"{key_a}\\{subkey}", f"{key_b}\\{subkey}")


def diff_to_human(diff: KeyDiff, *, key_a: str, key_b: str) -> list[str]:
    """Return the human-readable lines for one difference.

    Examples:
        >>> diff_to_human(ValueOnlyIn(DiffKind.ONLY_IN_A, "HKCU\\\\A", "v", "x"), key_a="HKCU\\\\A", key_b="HKCU\\\\B")
        ['  - HKCU\\\\A / v  (only in HKCU\\\\A)']
    """
    if isinstance(diff, ValueDiffers):
        return [f"  ~ {diff.path} / {diff.name}", f"    A: {json_safe(diff.data_a)}", f"    B: {json_safe(diff.data_b)}"]
    if isinstance(diff, ValueOnlyIn):
        if diff.kind == DiffKind.ONLY_IN_A:
            return [f"  - {diff.path} / {diff.name}  (only in {key_a})"]
        return [f"  + {diff.path} / {diff.name}  (only in {key_b})"]
    if diff.kind == DiffKind.SUBKEY_ONLY_IN_A:
        return [f"  - [KEY] {diff.path}  (only in {key_a})"]
    return [f"  + [KEY] {diff.path}  (only in {key_b})"]
