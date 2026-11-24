"""Helper functions for CLI commands - parsing, formatting, tree/diff operations.

The recursive walkers release the key handles they open once they leave a key
(see ``released_handles``), so a walk over a large subtree holds one handle per
level of depth instead of one per visited key. Every JSON output goes through
``echo_json``, which writes a document while its arrays are still being
produced (``JsonStream``), so list, tree, search and diff hold one path from
the root to the current item, never the whole result.
"""

import contextlib
import fnmatch
import itertools
import json
from collections.abc import Generator, Iterator, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import NamedTuple, cast

import rich_click as click
from rich.tree import Tree

from ._helpers import get_value_type_as_string, normalize_separators, resolve_key
from ._winreg_setup import RegData, reg_type_names_hashed_by_int, winreg
from .exceptions import RegistryKeyNotFoundError
from .records import RegValue
from .registry import Registry

TYPE_NAMES = list(reg_type_names_hashed_by_int.values())
_TYPE_NAME_TO_INT: Mapping[str, int] = MappingProxyType({v: k for k, v in reg_type_names_hashed_by_int.items()})
#: Largest value a REG_DWORD (unsigned 32-bit integer) can hold.
_REG_DWORD_MAX = 0xFFFFFFFF
_REG_QWORD_MAX = 0xFFFFFFFFFFFFFFFF


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
        # Checked here: on Windows winreg refuses an out-of-range int with an OverflowError, a
        # traceback for the user, while fake_winreg stores any int, so tests off Windows never see it.
        if reg_type == winreg.REG_DWORD and not (0 <= value <= _REG_DWORD_MAX):
            raise click.BadParameter(f'"{data}" overflows REG_DWORD (0..{_REG_DWORD_MAX})') from None
        if reg_type == winreg.REG_QWORD and not (0 <= value <= _REG_QWORD_MAX):
            raise click.BadParameter(f'"{data}" overflows REG_QWORD (0..{_REG_QWORD_MAX})') from None
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


@dataclass(frozen=True)
class JsonStream:
    """A JSON array whose items are produced while ``echo_json`` writes it.

    With ``omit_when_empty`` the key holding it is left out of its object when
    the array has no item, as ``tree`` does for a key without subkeys.
    """

    items: Iterator[object]
    omit_when_empty: bool = False


_JSON_INDENT = "  "
#: Size of the pieces ``echo_json`` hands to click: one write per piece, not one per token.
_JSON_PIECE_CHARS = 64 * 1024
_NO_ITEM = object()


def iter_json(value: object, level: int = 0) -> Iterator[str]:
    """Yield ``value`` as JSON text, the same characters as ``json.dumps(value, indent=2)``.

    A ``JsonStream`` is written as an array whose items are pulled one at a time.

    Examples:
        >>> "".join(iter_json({"a": JsonStream(iter([1, {"b": []}])), "c": {}}))
        '{\\n  "a": [\\n    1,\\n    {\\n      "b": []\\n    }\\n  ],\\n  "c": {}\\n}'
    """
    if isinstance(value, JsonStream):
        yield from _iter_json_array(value.items, level)
    elif isinstance(value, list):
        # isinstance checked the container; its items are whatever JSON value they hold.
        yield from _iter_json_array(iter(cast("list[object]", value)), level)
    elif isinstance(value, Mapping):
        yield from _iter_json_object(cast("Mapping[object, object]", value), level)
    else:
        yield json.dumps(value)


def _iter_json_array(items: Iterator[object], level: int) -> Iterator[str]:
    inner = _JSON_INDENT * (level + 1)
    opened = False
    for item in items:
        yield f",\n{inner}" if opened else f"[\n{inner}"
        opened = True
        yield from iter_json(item, level + 1)
    yield f"\n{_JSON_INDENT * level}]" if opened else "[]"


def _iter_json_object(mapping: Mapping[object, object], level: int) -> Iterator[str]:
    inner = _JSON_INDENT * (level + 1)
    opened = False
    for key, value in mapping.items():
        member = _present_member(value)
        if member is _NO_ITEM:
            continue
        yield f",\n{inner}" if opened else f"{{\n{inner}"
        opened = True
        yield f"{json.dumps(key)}: "
        yield from iter_json(member, level + 1)
    yield f"\n{_JSON_INDENT * level}}}" if opened else "{}"


def _present_member(value: object) -> object:
    """Return ``value`` to write, or ``_NO_ITEM`` for an empty ``omit_when_empty`` stream.

    Finding out whether a stream is empty takes its first item, so a non-empty
    one comes back as a new stream that starts with that item again.
    """
    if not (isinstance(value, JsonStream) and value.omit_when_empty):
        return value
    first = next(value.items, _NO_ITEM)
    if first is _NO_ITEM:
        return _NO_ITEM
    return JsonStream(itertools.chain([first], value.items))


def echo_json(value: object) -> None:
    """Print ``value`` as ``json.dumps(value, indent=2)`` would, while it is produced.

    Examples:
        >>> echo_json(JsonStream(iter([{"a": 1}, {"b": [2]}])))
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
        >>> echo_json(JsonStream(iter([])))
        []
    """
    piece: list[str] = []
    size = 0
    for chunk in iter_json(value):
        piece.append(chunk)
        size += len(chunk)
        if size >= _JSON_PIECE_CHARS:
            click.echo("".join(piece), nl=False)
            piece, size = [], 0
    click.echo("".join(piece))


@contextlib.contextmanager
def released_handles(registry: Registry, key: str) -> Generator[None, None, None]:
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


def list_document(registry: Registry, key: str, *, show_keys: bool, show_values: bool, recursive: bool) -> dict[str, object]:
    """Describe the JSON document for ``list``: the key, its subkeys and its values.

    The subkeys and values are ``JsonStream`` arrays, read from the registry
    only while ``echo_json`` writes them.
    """
    document: dict[str, object] = {"key": key}
    if show_keys:
        document["subkeys"] = JsonStream(_list_subkeys(registry, key, show_keys=show_keys, show_values=show_values, recursive=recursive))
    if show_values:
        document["values"] = JsonStream(_list_values(registry, key))
    return document


def _list_subkeys(registry: Registry, key: str, *, show_keys: bool, show_values: bool, recursive: bool) -> Iterator[object]:
    with released_handles(registry, key):
        for subkey in registry.subkeys(key):
            if recursive:
                yield list_document(registry, f"{key}\\{subkey}", show_keys=show_keys, show_values=show_values, recursive=recursive)
            else:
                yield subkey


def _list_values(registry: Registry, key: str) -> Iterator[object]:
    with released_handles(registry, key):
        for value in registry.values(key):
            yield value_to_json(value)


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


def tree_document(registry: Registry, key: str, max_depth: int, current_depth: int = 0) -> dict[str, object]:
    """Describe the JSON document for ``tree``: the key's name and, below ``max_depth``, its children.

    ``children`` is a ``JsonStream`` left out of the output when the key has no subkey.
    """
    # The last part of the path, so "HKLM/SOFTWARE" and "HKLM\\SOFTWARE" both name it SOFTWARE.
    document: dict[str, object] = {"name": normalize_separators(key).rsplit("\\", 1)[-1]}
    if current_depth < max_depth:
        document["children"] = JsonStream(_tree_children(registry, key, max_depth, current_depth), omit_when_empty=True)
    return document


def _tree_children(registry: Registry, key: str, max_depth: int, current_depth: int) -> Iterator[object]:
    # A key that vanishes during the walk ends its own children, not the whole tree.
    with released_handles(registry, key), contextlib.suppress(RegistryKeyNotFoundError):
        for subkey in registry.subkeys(key):
            yield tree_document(registry, f"{key}\\{subkey}", max_depth, current_depth + 1)


class CopyCount(NamedTuple):
    """What ``copy_recursive`` wrote below the destination key."""

    values: int
    keys: int


def copy_values(registry: Registry, src_key: str, dst_key: str) -> int:
    """Copy all values from src_key to dst_key and return how many were written."""
    written = 0
    for value in registry.values(src_key):
        registry.set_value(dst_key, value.name, value.data, value.reg_type)
        written += 1
    return written


def copy_recursive(registry: Registry, src_key: str, dst_key: str) -> CopyCount:
    """Recursively copy subkeys and their values; return the counts written below ``dst_key``."""
    values = keys = 0
    for subkey in registry.subkeys(src_key):
        src_child = f"{src_key}\\{subkey}"
        dst_child = f"{dst_key}\\{subkey}"
        with released_handles(registry, src_child), released_handles(registry, dst_child):
            registry.create_key(dst_child, parents=True)
            values += copy_values(registry, src_child, dst_child)
            below = copy_recursive(registry, src_child, dst_child)
        values += below.values
        keys += 1 + below.keys
    return CopyCount(values, keys)


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
