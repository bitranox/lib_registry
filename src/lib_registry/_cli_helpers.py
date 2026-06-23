"""Helper functions for CLI commands — parsing, formatting, tree/diff operations."""

import fnmatch

import rich_click as click
from rich.tree import Tree

from .exceptions import RegistryKeyNotFoundError
from .registry import Registry
from ._winreg_setup import reg_type_names_hashed_by_int, winreg
from ._helpers import get_value_type_as_string

_TYPE_NAMES = list(reg_type_names_hashed_by_int.values())
_TYPE_NAME_TO_INT = {v: k for k, v in reg_type_names_hashed_by_int.items()}


def json_safe(obj: object) -> object:
    """Make non-serializable objects JSON-safe."""
    if isinstance(obj, bytes):
        return obj.hex()
    return str(obj)


def parse_value_and_type(data: str, type_name: str | None) -> tuple[str | int | bytes | list[str] | None, int | None]:
    """Convert CLI string data to the appropriate Python type.

    Without ``--type``, data is always stored as REG_SZ (string).
    Use ``--type REG_DWORD`` explicitly for integers.
    """
    if type_name is None:
        return data, None

    reg_type = _TYPE_NAME_TO_INT[type_name.upper()]

    if reg_type in (winreg.REG_DWORD, winreg.REG_QWORD):
        try:
            value = int(data, 0)
        except ValueError:
            raise click.BadParameter(f'"{data}" is not a valid integer for {type_name}') from None
        if reg_type == winreg.REG_DWORD and not (0 <= value <= 0xFFFFFFFF):
            raise click.BadParameter(f'"{data}" overflows REG_DWORD (0..4294967295)') from None
        return value, reg_type
    if reg_type == winreg.REG_BINARY:
        return data.encode("utf-8"), reg_type
    if reg_type == winreg.REG_MULTI_SZ:
        return data.split("\\0"), reg_type
    if reg_type == winreg.REG_NONE:
        return None, reg_type
    return data, reg_type


def list_human(registry: Registry, key: str, show_keys: bool, show_values: bool, recursive: bool, indent: int) -> None:
    """Print key contents in human-readable format."""
    prefix = "  " * indent
    if show_keys:
        for subkey in registry.subkeys(key):
            click.echo(f"{prefix}[KEY] {subkey}")
            if recursive:
                list_human(registry, f"{key}\\{subkey}", show_keys, show_values, recursive, indent + 1)
    if show_values:
        for name, data, reg_type in registry.values(key):
            type_str = get_value_type_as_string(reg_type)
            click.echo(f"{prefix}[{type_str}] {name} = {data}")


def list_to_dict(registry: Registry, key: str, show_keys: bool, show_values: bool, recursive: bool) -> dict[str, object]:
    """Build a dict representation for JSON output."""
    result: dict[str, object] = {"key": key}
    if show_keys:
        subkeys: list[object] = []
        for subkey in registry.subkeys(key):
            if recursive:
                subkeys.append(list_to_dict(registry, f"{key}\\{subkey}", show_keys, show_values, recursive))
            else:
                subkeys.append(subkey)
        result["subkeys"] = subkeys
    if show_values:
        values: list[dict[str, object]] = []
        for name, data, reg_type in registry.values(key):
            values.append({"name": name, "data": json_safe(data), "type": get_value_type_as_string(reg_type)})
        result["values"] = values
    return result


def search_recursive(
    registry: Registry,
    key: str,
    name_pattern: str | None,
    data_pattern: str | None,
    collector: list[dict[str, object]] | None = None,
) -> None:
    """Recursively search values under a key, printing or collecting matches."""
    try:
        for val_name, val_data, reg_type in registry.values(key):
            if name_pattern and not fnmatch.fnmatch(val_name, name_pattern):
                continue
            if data_pattern and not fnmatch.fnmatch(str(val_data), data_pattern):
                continue
            if collector is not None:
                collector.append(
                    {
                        "key": key,
                        "name": val_name,
                        "data": json_safe(val_data),
                        "type": get_value_type_as_string(reg_type),
                    }
                )
            else:
                type_str = get_value_type_as_string(reg_type)
                click.echo(f"{key}  [{type_str}] {val_name} = {val_data}")
    except RegistryKeyNotFoundError:
        return

    try:
        for subkey in registry.subkeys(key):
            child_path = f"{key}\\{subkey}"
            search_recursive(registry, child_path, name_pattern, data_pattern, collector)
    except RegistryKeyNotFoundError:
        return


def build_tree(registry: Registry, key: str, tree: Tree, max_depth: int, current_depth: int = 0) -> None:
    """Recursively build a Rich Tree for display."""
    if current_depth >= max_depth:
        return
    try:
        for subkey in registry.subkeys(key):
            branch = tree.add(f"[bold]{subkey}[/bold]")
            build_tree(registry, f"{key}\\{subkey}", branch, max_depth, current_depth + 1)
    except RegistryKeyNotFoundError:
        return


def tree_to_dict(registry: Registry, key: str, max_depth: int, current_depth: int = 0) -> dict[str, object]:
    """Build a dict tree for JSON output."""
    result: dict[str, object] = {"name": key.rsplit("\\", 1)[-1] if "\\" in key else key}
    if current_depth >= max_depth:
        return result
    children: list[dict[str, object]] = []
    try:
        for subkey in registry.subkeys(key):
            children.append(tree_to_dict(registry, f"{key}\\{subkey}", max_depth, current_depth + 1))
    except RegistryKeyNotFoundError:
        pass
    if children:
        result["children"] = children
    return result


def copy_values(registry: Registry, src_key: str, dst_key: str) -> None:
    """Copy all values from src_key to dst_key."""
    for name, data, reg_type in registry.values(src_key):
        registry.set_value(dst_key, name, data, reg_type)


def copy_recursive(registry: Registry, src_key: str, dst_key: str) -> None:
    """Recursively copy subkeys and values."""
    for subkey in registry.subkeys(src_key):
        src_child = f"{src_key}\\{subkey}"
        dst_child = f"{dst_key}\\{subkey}"
        registry.create_key(dst_child, parents=True)
        copy_values(registry, src_child, dst_child)
        copy_recursive(registry, src_child, dst_child)


def diff_keys(registry: Registry, key_a: str, key_b: str) -> list[dict[str, object]]:
    """Compare two registry keys and return a list of differences."""
    diffs: list[dict[str, object]] = []

    vals_a = {name: (data, reg_type) for name, data, reg_type in registry.values(key_a)}
    vals_b = {name: (data, reg_type) for name, data, reg_type in registry.values(key_b)}

    for name in sorted(set(vals_a) | set(vals_b)):
        if name in vals_a and name not in vals_b:
            diffs.append({"kind": "only_in_a", "path": key_a, "name": name, "value": json_safe(vals_a[name][0])})
        elif name in vals_b and name not in vals_a:
            diffs.append({"kind": "only_in_b", "path": key_b, "name": name, "value": json_safe(vals_b[name][0])})
        elif vals_a[name] != vals_b[name]:
            diffs.append(
                {
                    "kind": "value_differs",
                    "path": key_a,
                    "name": name,
                    "value_a": json_safe(vals_a[name][0]),
                    "value_b": json_safe(vals_b[name][0]),
                }
            )

    subs_a = set(registry.subkeys(key_a))
    subs_b = set(registry.subkeys(key_b))

    for subkey in sorted(subs_a - subs_b):
        diffs.append({"kind": "subkey_only_in_a", "path": f"{key_a}\\{subkey}"})
    for subkey in sorted(subs_b - subs_a):
        diffs.append({"kind": "subkey_only_in_b", "path": f"{key_b}\\{subkey}"})

    for subkey in sorted(subs_a & subs_b):
        diffs.extend(diff_keys(registry, f"{key_a}\\{subkey}", f"{key_b}\\{subkey}"))

    return diffs
