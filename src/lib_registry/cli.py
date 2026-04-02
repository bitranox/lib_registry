"""CLI adapter wiring registry helpers into a rich-click interface.

Expose a stable command-line surface using rich-click for consistent,
beautiful terminal output. The CLI delegates to the registry module while
maintaining clean separation of concerns.
"""

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
from ._cli_helpers import (
    _TYPE_NAMES,
    build_tree,
    copy_recursive,
    copy_values,
    diff_keys,
    json_safe,
    list_human,
    list_to_dict,
    parse_value_and_type,
    search_recursive,
    tree_to_dict,
)
from ._helpers import get_key_as_string, get_value_type_as_string
from .exceptions import (
    RegistryError,
    RegistryValueDeleteError,
    RegistryValueNotFoundError,
)
from .registry import Registry

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
    return ctx.ensure_object(CliContext).json_output


def _is_quiet(ctx: click.Context) -> bool:
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
@click.option("--traceback/--no-traceback", is_flag=True, default=True, help="Show full Python traceback on errors (default: enabled)")
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
# Commands
# ---------------------------------------------------------------------------


@cli.command("info", context_settings=CLICK_CONTEXT_SETTINGS)
def cli_info() -> None:
    """Print resolved metadata so users can inspect installation details."""
    __init__conf__.print_info()


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
        click.echo(json.dumps({"name": value_name, "data": json_safe(data), "type": get_value_type_as_string(reg_type)}))
    elif show_type:
        data, reg_type = registry.get_value_ex(key, value_name)
        click.echo(f"{get_value_type_as_string(reg_type)}: {data}")
    else:
        click.echo(registry.get_value(key, value_name))


@cli.command("set", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("key")
@click.argument("value_name")
@click.argument("data")
@click.option("--type", "value_type", type=click.Choice(_TYPE_NAMES, case_sensitive=False), default=None, help="Registry type (REG_SZ if omitted)")
@click.option("--default", "use_default", is_flag=True, help="Write the unnamed default value (VALUE_NAME ignored)")
@click.pass_context
def cli_set(ctx: click.Context, key: str, value_name: str, data: str, value_type: str | None, use_default: bool) -> None:
    """Write a registry value. Stored as REG_SZ unless --type is given."""
    registry = _make_registry(ctx)
    if use_default:
        value_name = ""
    parsed_data, parsed_type = parse_value_and_type(data, value_type)
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
        result = list_to_dict(registry, key, show_all or show_keys, show_all or show_values, recursive)
        click.echo(json.dumps(result, indent=2, default=json_safe))
    else:
        list_human(registry, key, show_all or show_keys, show_all or show_values, recursive, indent=0)


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
    _make_registry(ctx).create_key(key, parents=parents)


@cli.command("delete-key", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("key")
@click.option("--recursive", is_flag=True, help="Delete subkeys recursively")
@click.option("--force", is_flag=True, help="Suppress error if key does not exist")
@click.pass_context
def cli_delete_key(ctx: click.Context, key: str, recursive: bool, force: bool) -> None:
    """Delete a registry key."""
    _make_registry(ctx).delete_key(key, delete_subkeys=recursive, missing_ok=force)


@cli.command("export", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("key")
@click.argument("file", type=click.Path())
@click.pass_context
def cli_export(ctx: click.Context, key: str, file: str) -> None:
    """Export a registry key subtree to a file."""
    _make_registry(ctx).save_key(key, file)


@cli.command("import", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("key")
@click.argument("sub_key")
@click.argument("file", type=click.Path(exists=True))
@click.pass_context
def cli_import(ctx: click.Context, key: str, sub_key: str, file: str) -> None:
    """Import a registry subtree from a file into KEY\\SUB_KEY."""
    _make_registry(ctx).load_key(key, sub_key, file)


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
        search_recursive(registry, key, name_pattern, data_pattern, collector=results)
        click.echo(json.dumps(results, indent=2, default=json_safe))
    else:
        search_recursive(registry, key, name_pattern, data_pattern)


@cli.command("users", context_settings=CLICK_CONTEXT_SETTINGS)
@click.pass_context
def cli_users(ctx: click.Context) -> None:
    """List Windows user SIDs with resolved usernames."""
    registry = _make_registry(ctx)
    entries = [(sid, _resolve_username(registry, sid)) for sid in registry.sids()]
    if _is_json(ctx):
        click.echo(json.dumps([{"sid": s, "username": u} for s, u in entries], indent=2))
    else:
        table = Table(title="Registry Users")
        table.add_column("SID", style="cyan")
        table.add_column("Username", style="green")
        for sid, username in entries:
            table.add_row(sid, username)
        console.print(table)


@cli.command("sid", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("sid_value")
@click.pass_context
def cli_sid(ctx: click.Context, sid_value: str) -> None:
    """Resolve a SID to a username."""
    registry = _make_registry(ctx)
    username = registry.username_from_sid(sid_value)
    if _is_json(ctx):
        click.echo(json.dumps({"sid": sid_value, "username": username}))
    else:
        click.echo(username)


@cli.command("whoami", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("username")
@click.pass_context
def cli_whoami(ctx: click.Context, username: str) -> None:
    """Resolve a username to its SID (reverse lookup)."""
    registry = _make_registry(ctx)
    sid = registry.sid_from_username(username)
    if _is_json(ctx):
        click.echo(json.dumps({"username": username, "sid": sid}))
    else:
        click.echo(sid)


@cli.command("tree", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("key")
@click.option("--depth", default=3, type=int, help="Maximum depth to display (default: 3)")
@click.pass_context
def cli_tree(ctx: click.Context, key: str, depth: int) -> None:
    """Display a visual tree of registry keys."""
    registry = _make_registry(ctx)
    if _is_json(ctx):
        result = tree_to_dict(registry, key, depth)
        click.echo(json.dumps(result, indent=2))
    else:
        label = get_key_as_string(key)
        tree = Tree(f"[bold]{label}[/bold]")
        build_tree(registry, key, tree, depth)
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
    copy_values(registry, src_key, dst_key)
    if recursive:
        copy_recursive(registry, src_key, dst_key)
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
    diffs = diff_keys(registry, key_a, key_b)
    if _is_json(ctx):
        click.echo(json.dumps(diffs, indent=2, default=json_safe))
    elif not diffs:
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
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_username(registry: Registry, sid: str) -> str:
    """Resolve username from SID, returning '(unknown)' on failure."""
    try:
        return registry.username_from_sid(sid)
    except RegistryError:
        return "(unknown)"


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
        tb = Traceback.from_exception(type(exc), exc, exc.__traceback__, show_locals=True, width=120)
        console.print(tb)
    else:
        console.print(f"Error: {type(exc).__name__}: {exc}", style=_ERROR_STYLE)
