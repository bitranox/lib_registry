"""CLI adapter wiring registry helpers into a rich-click interface.

Expose a stable command-line surface using rich-click for consistent,
beautiful terminal output. The CLI delegates to the registry module while
maintaining clean separation of concerns.

Note:
    The CLI is the primary adapter for local development workflows. Packaging
    targets register the console script defined in __init__conf__. The module
    entry point (python -m) reuses the same helpers for consistency.

"""

from __future__ import annotations

import fnmatch
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass

import rich_click as click
from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.traceback import Traceback, install as install_rich_traceback
from rich.tree import Tree

from . import __init__conf__
from .registry import (
    Registry,
    RegistryError,
    RegistryKeyNotFoundError,
    RegistryValueDeleteError,
    RegistryValueNotFoundError,
    get_key_as_string,
    get_value_type_as_string,
    reg_type_names_hashed_by_int,
    winreg,
)

__all__ = [
    "CLICK_CONTEXT_SETTINGS",
    "CliContext",
    "cli",
    "console",
    "main",
]

#: Shared Click context flags for consistent help output.
CLICK_CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

#: Console for rich output
console = Console()

#: Style for error messages when traceback is suppressed
_ERROR_STYLE = Style(color="red", bold=True)

#: Valid type names for --type option
_TYPE_NAMES = list(reg_type_names_hashed_by_int.values())
_TYPE_NAME_TO_INT = {v: k for k, v in reg_type_names_hashed_by_int.items()}


@dataclass
class CliContext:
    """Typed context object for Click's ``ctx.obj``.

    Attributes:
        traceback: Whether to show full Python traceback on errors.
        quiet: Suppress non-error output.
        json_output: Emit JSON instead of human-readable output.
        computer: Remote computer name for registry connections.

    """

    traceback: bool = True
    quiet: bool = False
    json_output: bool = False
    computer: str | None = None


def _exit_code_from(exc: SystemExit) -> int:
    """Extract integer exit code from SystemExit.

    Examples:
        >>> _exit_code_from(SystemExit(0))
        0
        >>> _exit_code_from(SystemExit(42))
        42
        >>> _exit_code_from(SystemExit("error"))
        1
        >>> _exit_code_from(SystemExit(None))
        0

    """
    if isinstance(exc.code, int):
        return exc.code
    return 1 if exc.code else 0


def _make_registry(ctx: click.Context) -> Registry:
    """Create a Registry using the global --computer option if set."""
    cli_ctx = ctx.ensure_object(CliContext)
    if cli_ctx.computer:
        return Registry(computer_name=cli_ctx.computer)
    return Registry()


def _is_json(ctx: click.Context) -> bool:
    """Check if --json output was requested."""
    return ctx.ensure_object(CliContext).json_output


def _is_quiet(ctx: click.Context) -> bool:
    """Check if --quiet was requested."""
    return ctx.ensure_object(CliContext).quiet


# ---------------------------------------------------------------------------
# Root command group
# ---------------------------------------------------------------------------


@click.group(
    help=__init__conf__.title,
    context_settings=CLICK_CONTEXT_SETTINGS,
    invoke_without_command=True,
)
@click.version_option(
    version=__init__conf__.version,
    prog_name=__init__conf__.shell_command,
    message=f"{__init__conf__.shell_command} version {__init__conf__.version}",
)
@click.option(
    "--traceback/--no-traceback",
    is_flag=True,
    default=True,
    help="Show full Python traceback on errors (default: enabled)",
)
@click.option("-q", "--quiet", is_flag=True, default=False, help="Suppress non-error output")
@click.option("--json", "json_output", is_flag=True, default=False, help="Emit JSON output (for scripting)")
@click.option("--computer", default=None, help="Connect to remote computer registry")
@click.pass_context
def cli(ctx: click.Context, traceback: bool, quiet: bool, json_output: bool, computer: str | None) -> None:
    """Root command storing global flags.

    Examples:
        >>> from click.testing import CliRunner
        >>> runner = CliRunner()
        >>> result = runner.invoke(cli, ["info"])
        >>> result.exit_code
        0

    """
    cli_ctx = ctx.ensure_object(CliContext)
    cli_ctx.traceback = traceback
    cli_ctx.quiet = quiet
    cli_ctx.json_output = json_output
    cli_ctx.computer = computer

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ---------------------------------------------------------------------------
# Info command
# ---------------------------------------------------------------------------


@cli.command("info", context_settings=CLICK_CONTEXT_SETTINGS)
def cli_info() -> None:
    """Print resolved metadata so users can inspect installation details."""
    __init__conf__.print_info()


# ---------------------------------------------------------------------------
# Registry key/value commands
# ---------------------------------------------------------------------------


@cli.command("get", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("key")
@click.argument("value_name", default="")
@click.option("--type", "show_type", is_flag=True, help="Also display the registry type")
@click.option("--default", "use_default", is_flag=True, help="Read the unnamed default value")
@click.pass_context
def cli_get(ctx: click.Context, key: str, value_name: str, show_type: bool, use_default: bool) -> None:
    """Read a registry value and print it to stdout."""
    registry = _make_registry(ctx)
    if use_default:
        value_name = ""
    if _is_json(ctx):
        data, reg_type = registry.get_value_ex(key, value_name)
        click.echo(json.dumps({"name": value_name, "data": _json_safe(data), "type": get_value_type_as_string(reg_type)}))
    elif show_type:
        data, reg_type = registry.get_value_ex(key, value_name)
        click.echo(f"{get_value_type_as_string(reg_type)}: {data}")
    else:
        click.echo(registry.get_value(key, value_name))


@cli.command("set", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("key")
@click.argument("value_name")
@click.argument("data")
@click.option(
    "--type",
    "value_type",
    type=click.Choice(_TYPE_NAMES, case_sensitive=False),
    default=None,
    help="Registry type (REG_SZ if omitted)",
)
@click.option("--default", "use_default", is_flag=True, help="Write the unnamed default value (VALUE_NAME ignored)")
@click.pass_context
def cli_set(ctx: click.Context, key: str, value_name: str, data: str, value_type: str | None, use_default: bool) -> None:
    """Write a registry value. Stored as REG_SZ unless --type is given."""
    registry = _make_registry(ctx)
    if use_default:
        value_name = ""
    parsed_data, parsed_type = _parse_value_and_type(data, value_type)
    registry.set_value(key, value_name, parsed_data, parsed_type)


@cli.command("delete-value", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("key")
@click.argument("value_name")
@click.option("--force", is_flag=True, help="Suppress error if value does not exist")
@click.pass_context
def cli_delete_value(ctx: click.Context, key: str, value_name: str, force: bool) -> None:
    """Delete a registry value."""
    registry = _make_registry(ctx)
    try:
        registry.delete_value(key, value_name)
    except (RegistryValueNotFoundError, RegistryValueDeleteError):
        if not force:
            raise


@cli.command("list", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("key")
@click.option("--keys", "show_keys", is_flag=True, help="Show subkeys only")
@click.option("--values", "show_values", is_flag=True, help="Show values only")
@click.option("--recursive", "-r", is_flag=True, help="Recurse into subkeys")
@click.pass_context
def cli_list(ctx: click.Context, key: str, show_keys: bool, show_values: bool, recursive: bool) -> None:
    """List subkeys and values of a registry key."""
    registry = _make_registry(ctx)
    show_all = not show_keys and not show_values

    if _is_json(ctx):
        result = _list_to_dict(registry, key, show_all or show_keys, show_all or show_values, recursive)
        click.echo(json.dumps(result, indent=2, default=_json_safe))
    else:
        _list_human(registry, key, show_all or show_keys, show_all or show_values, recursive, indent=0)


@cli.command("exists", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("key")
@click.pass_context
def cli_exists(ctx: click.Context, key: str) -> None:
    """Check if a registry key exists. Exit code 0 if yes, 1 if no."""
    registry = _make_registry(ctx)
    if not registry.key_exist(key):
        raise SystemExit(1)


@cli.command("create-key", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("key")
@click.option("--parents", is_flag=True, help="Create intermediate parent keys")
@click.pass_context
def cli_create_key(ctx: click.Context, key: str, parents: bool) -> None:
    """Create a registry key."""
    registry = _make_registry(ctx)
    registry.create_key(key, parents=parents)


@cli.command("delete-key", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("key")
@click.option("--recursive", is_flag=True, help="Delete subkeys recursively")
@click.option("--force", is_flag=True, help="Suppress error if key does not exist")
@click.pass_context
def cli_delete_key(ctx: click.Context, key: str, recursive: bool, force: bool) -> None:
    """Delete a registry key."""
    registry = _make_registry(ctx)
    registry.delete_key(key, delete_subkeys=recursive, missing_ok=force)


@cli.command("export", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("key")
@click.argument("file", type=click.Path())
@click.pass_context
def cli_export(ctx: click.Context, key: str, file: str) -> None:
    """Export a registry key subtree to a file."""
    registry = _make_registry(ctx)
    registry.save_key(key, file)


@cli.command("import", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("key")
@click.argument("sub_key")
@click.argument("file", type=click.Path(exists=True))
@click.pass_context
def cli_import(ctx: click.Context, key: str, sub_key: str, file: str) -> None:
    """Import a registry subtree from a file into KEY\\SUB_KEY."""
    registry = _make_registry(ctx)
    registry.load_key(key, sub_key, file)


@cli.command("search", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("key")
@click.option("--name", "name_pattern", default=None, help="Filter values by name (glob pattern)")
@click.option("--data", "data_pattern", default=None, help="Filter values by data content (glob pattern)")
@click.pass_context
def cli_search(ctx: click.Context, key: str, name_pattern: str | None, data_pattern: str | None) -> None:
    """Search for values matching a pattern under a registry key."""
    registry = _make_registry(ctx)
    if _is_json(ctx):
        results: list[dict[str, object]] = []
        _search_recursive(registry, key, name_pattern, data_pattern, collector=results)
        click.echo(json.dumps(results, indent=2, default=_json_safe))
    else:
        _search_recursive(registry, key, name_pattern, data_pattern)


@cli.command("users", context_settings=CLICK_CONTEXT_SETTINGS)
@click.pass_context
def cli_users(ctx: click.Context) -> None:
    """List Windows user SIDs with resolved usernames."""
    registry = _make_registry(ctx)
    entries: list[tuple[str, str]] = []
    for sid in registry.sids():
        try:
            username = registry.username_from_sid(sid)
        except RegistryError:
            username = "(unknown)"
        entries.append((sid, username))

    if _is_json(ctx):
        click.echo(json.dumps([{"sid": s, "username": u} for s, u in entries], indent=2))
    else:
        table = Table(title="Registry Users")
        table.add_column("SID", style="cyan")
        table.add_column("Username", style="green")
        for sid, username in entries:
            table.add_row(sid, username)
        console.print(table)


@cli.command("tree", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("key")
@click.option("--depth", default=3, type=int, help="Maximum depth to display (default: 3)")
@click.pass_context
def cli_tree(ctx: click.Context, key: str, depth: int) -> None:
    """Display a visual tree of registry keys."""
    registry = _make_registry(ctx)
    if _is_json(ctx):
        result = _tree_to_dict(registry, key, depth)
        click.echo(json.dumps(result, indent=2))
    else:
        label = get_key_as_string(key)
        tree = Tree(f"[bold]{label}[/bold]")
        _build_tree(registry, key, tree, depth)
        console.print(tree)


@cli.command("copy", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("src_key")
@click.argument("dst_key")
@click.option("--recursive", is_flag=True, help="Copy subkeys recursively")
@click.pass_context
def cli_copy(ctx: click.Context, src_key: str, dst_key: str, recursive: bool) -> None:
    """Copy values (and optionally subkeys) from SRC_KEY to DST_KEY."""
    registry = _make_registry(ctx)
    registry.create_key(dst_key, parents=True)
    _copy_values(registry, src_key, dst_key)
    if recursive:
        _copy_recursive(registry, src_key, dst_key)
    if not _is_quiet(ctx):
        click.echo(f"Copied {src_key} -> {dst_key}")


@cli.command("rename", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("key")
@click.argument("old_name")
@click.argument("new_name")
@click.pass_context
def cli_rename(ctx: click.Context, key: str, old_name: str, new_name: str) -> None:
    """Rename a registry value (copy + delete)."""
    registry = _make_registry(ctx)
    data, reg_type = registry.get_value_ex(key, old_name)
    registry.set_value(key, new_name, data, reg_type)
    registry.delete_value(key, old_name)
    if not _is_quiet(ctx):
        click.echo(f"Renamed {old_name} -> {new_name}")


@cli.command("diff", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("key_a")
@click.argument("key_b")
@click.pass_context
def cli_diff(ctx: click.Context, key_a: str, key_b: str) -> None:
    """Compare two registry key subtrees and show differences."""
    registry = _make_registry(ctx)
    diffs = _diff_keys(registry, key_a, key_b)

    if _is_json(ctx):
        click.echo(json.dumps(diffs, indent=2, default=_json_safe))
    else:
        if not diffs:
            click.echo("No differences found.")
        else:
            for diff in diffs:
                kind = diff["kind"]
                if kind == "only_in_a":
                    click.echo(f"  - {diff['path']}  (only in {key_a})")
                elif kind == "only_in_b":
                    click.echo(f"  + {diff['path']}  (only in {key_b})")
                elif kind == "value_differs":
                    click.echo(f"  ~ {diff['path']} / {diff['name']}")
                    click.echo(f"    A: {diff['value_a']}")
                    click.echo(f"    B: {diff['value_b']}")
                elif kind == "subkey_only_in_a":
                    click.echo(f"  - [KEY] {diff['path']}  (only in {key_a})")
                elif kind == "subkey_only_in_b":
                    click.echo(f"  + [KEY] {diff['path']}  (only in {key_b})")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_safe(obj: object) -> object:
    """Make non-serializable objects JSON-safe."""
    if isinstance(obj, bytes):
        return obj.hex()
    return str(obj)


def _parse_value_and_type(data: str, type_name: str | None) -> tuple[str | int | bytes | list[str] | None, int | None]:
    """Convert CLI string data to the appropriate Python type based on the registry type name.

    Without ``--type``, data is always stored as REG_SZ (string).
    Use ``--type REG_DWORD`` explicitly for integers.
    """
    if type_name is None:
        return data, None

    reg_type = _TYPE_NAME_TO_INT[type_name.upper()]

    if reg_type in (winreg.REG_DWORD, winreg.REG_QWORD):
        try:
            value = int(data, 0)  # Accepts decimal, hex (0x...), octal (0o...)
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


def _list_human(registry: Registry, key: str, show_keys: bool, show_values: bool, recursive: bool, indent: int) -> None:
    """Print key contents in human-readable format."""
    prefix = "  " * indent
    if show_keys:
        for subkey in registry.subkeys(key):
            click.echo(f"{prefix}[KEY] {subkey}")
            if recursive:
                _list_human(registry, f"{key}\\{subkey}", show_keys, show_values, recursive, indent + 1)
    if show_values:
        for name, data, reg_type in registry.values(key):
            type_str = get_value_type_as_string(reg_type)
            click.echo(f"{prefix}[{type_str}] {name} = {data}")


def _list_to_dict(registry: Registry, key: str, show_keys: bool, show_values: bool, recursive: bool) -> dict[str, object]:
    """Build a dict representation for JSON output."""
    result: dict[str, object] = {"key": key}
    if show_keys:
        subkeys: list[object] = []
        for subkey in registry.subkeys(key):
            if recursive:
                subkeys.append(_list_to_dict(registry, f"{key}\\{subkey}", show_keys, show_values, recursive))
            else:
                subkeys.append(subkey)
        result["subkeys"] = subkeys
    if show_values:
        values: list[dict[str, object]] = []
        for name, data, reg_type in registry.values(key):
            values.append({"name": name, "data": _json_safe(data), "type": get_value_type_as_string(reg_type)})
        result["values"] = values
    return result


def _search_recursive(
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
                        "data": _json_safe(val_data),
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
            _search_recursive(registry, child_path, name_pattern, data_pattern, collector)
    except RegistryKeyNotFoundError:
        return


def _build_tree(registry: Registry, key: str, tree: Tree, max_depth: int, current_depth: int = 0) -> None:
    """Recursively build a Rich Tree for display."""
    if current_depth >= max_depth:
        return
    try:
        for subkey in registry.subkeys(key):
            branch = tree.add(f"[bold]{subkey}[/bold]")
            _build_tree(registry, f"{key}\\{subkey}", branch, max_depth, current_depth + 1)
    except RegistryKeyNotFoundError:
        return


def _tree_to_dict(registry: Registry, key: str, max_depth: int, current_depth: int = 0) -> dict[str, object]:
    """Build a dict tree for JSON output."""
    result: dict[str, object] = {"name": key.rsplit("\\", 1)[-1] if "\\" in key else key}
    if current_depth >= max_depth:
        return result
    children: list[dict[str, object]] = []
    try:
        for subkey in registry.subkeys(key):
            children.append(_tree_to_dict(registry, f"{key}\\{subkey}", max_depth, current_depth + 1))
    except RegistryKeyNotFoundError:
        pass
    if children:
        result["children"] = children
    return result


def _copy_values(registry: Registry, src_key: str, dst_key: str) -> None:
    """Copy all values from src_key to dst_key."""
    for name, data, reg_type in registry.values(src_key):
        registry.set_value(dst_key, name, data, reg_type)


def _copy_recursive(registry: Registry, src_key: str, dst_key: str) -> None:
    """Recursively copy subkeys and values."""
    for subkey in registry.subkeys(src_key):
        src_child = f"{src_key}\\{subkey}"
        dst_child = f"{dst_key}\\{subkey}"
        registry.create_key(dst_child, parents=True)
        _copy_values(registry, src_child, dst_child)
        _copy_recursive(registry, src_child, dst_child)


def _diff_keys(registry: Registry, key_a: str, key_b: str) -> list[dict[str, object]]:
    """Compare two registry keys and return a list of differences."""
    diffs: list[dict[str, object]] = []

    # Compare values
    vals_a = {name: (data, reg_type) for name, data, reg_type in registry.values(key_a)}
    vals_b = {name: (data, reg_type) for name, data, reg_type in registry.values(key_b)}

    for name in sorted(set(vals_a) | set(vals_b)):
        if name in vals_a and name not in vals_b:
            diffs.append({"kind": "only_in_a", "path": key_a, "name": name, "value": _json_safe(vals_a[name][0])})
        elif name in vals_b and name not in vals_a:
            diffs.append({"kind": "only_in_b", "path": key_b, "name": name, "value": _json_safe(vals_b[name][0])})
        elif vals_a[name] != vals_b[name]:
            diffs.append(
                {
                    "kind": "value_differs",
                    "path": key_a,
                    "name": name,
                    "value_a": _json_safe(vals_a[name][0]),
                    "value_b": _json_safe(vals_b[name][0]),
                }
            )

    # Compare subkeys
    subs_a = set(registry.subkeys(key_a))
    subs_b = set(registry.subkeys(key_b))

    for subkey in sorted(subs_a - subs_b):
        diffs.append({"kind": "subkey_only_in_a", "path": f"{key_a}\\{subkey}"})
    for subkey in sorted(subs_b - subs_a):
        diffs.append({"kind": "subkey_only_in_b", "path": f"{key_b}\\{subkey}"})

    # Recurse into common subkeys
    for subkey in sorted(subs_a & subs_b):
        diffs.extend(_diff_keys(registry, f"{key_a}\\{subkey}", f"{key_b}\\{subkey}"))

    return diffs


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the CLI and return the exit code.

    Examples:
        >>> main(["info"])  # doctest: +ELLIPSIS
        Info for lib_registry:
        ...
        0

    """
    argv_list = list(argv) if argv else sys.argv[1:]
    show_traceback = "--no-traceback" not in argv_list

    if show_traceback:
        install_rich_traceback(show_locals=True)

    try:
        cli(args=argv, standalone_mode=False, prog_name=__init__conf__.shell_command)
        return 0
    except SystemExit as exc:
        return _exit_code_from(exc)
    except Exception as exc:
        _print_error(exc, show_traceback=show_traceback)
        return 1


def _print_error(exc: Exception, *, show_traceback: bool) -> None:
    """Print error to console with or without full traceback."""
    if show_traceback:
        tb = Traceback.from_exception(
            type(exc),
            exc,
            exc.__traceback__,
            show_locals=True,
            width=120,
        )
        console.print(tb)
    else:
        console.print(f"Error: {type(exc).__name__}: {exc}", style=_ERROR_STYLE)
