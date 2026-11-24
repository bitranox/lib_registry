# Module Reference: lib_registry

## Status

Complete

## Links & References
**Repository:** https://github.com/bitranox/lib_registry
**Related Files:**

* src/lib_registry/registry.py (the `Registry` class)
* src/lib_registry/exceptions.py (exception hierarchy)
* src/lib_registry/records.py (`NamedTuple` records)
* src/lib_registry/_helpers.py (key-path helpers)
* src/lib_registry/_winreg_setup.py (winreg / fake_winreg selection, constants, lookup tables)
* src/lib_registry/cli.py (rich-click CLI adapter)
* src/lib_registry/_cli_helpers.py (CLI parsing, walkers, JSON writer)
* src/lib_registry/typed_click.py (strict-typed click decorator wrappers)
* src/lib_registry/__main__.py
* src/lib_registry/__init__.py
* src/lib_registry/__init__conf__.py
* tests/test_cli.py, tests/test_walks.py, tests/test_remote.py, tests/test_metadata.py,
  tests/test_module_entry.py, tests/test_packaging.py, tests/test_platform_markers.py

---

## Problem Statement

Python's built-in `winreg` module provides low-level access to the Windows
registry but requires manual handle management, verbose error handling, and
platform-specific code. `lib_registry` wraps `winreg` (and `fake_winreg` on
non-Windows platforms) with a high-level `Registry` class that provides
connection caching, automatic type detection, recursive operations, and a
cross-platform development experience.

## Solution Overview

* `registry.py` contains the `Registry` class and re-exports the names below
  it.
* `exceptions.py` holds the exception hierarchy, `records.py` the `NamedTuple`
  records, `_helpers.py` the key-path helpers (including `normalize_separators`
  for forward-slash support).
* `_winreg_setup.py` picks `winreg` on Windows or `fake_winreg` elsewhere and
  holds the `RegData` alias, the `HKEY_*`/`REG_*`/`KEY_*` constants, the named
  winerror constants and the lookup tables.
* `cli.py` provides a rich-click CLI adapter with 18 commands for registry
  operations, delegating to `Registry` methods; `_cli_helpers.py` holds its
  value parsing, the recursive walkers and the streaming JSON writer.
* `__main__.py` delegates to `cli.main()` for `python -m` execution.
* `__init__.py` re-exports the public API for library consumers.
* `__init__conf__.py` holds static metadata constants synced from
  `pyproject.toml` by automation.

---

## Architecture Integration

**Layer Structure** (the import-linter `layers` contract in `pyproject.toml`,
each layer importing only from those below it):
```
cli.py (and __main__.py)
_cli_helpers.py
registry.py
_helpers.py
records.py
exceptions.py | _winreg_setup.py   -> winreg / fake_winreg
```

**Data Flow:**
1. Library consumers import `Registry` from `lib_registry` and call methods
   directly. Both `/` and `\` are accepted in key paths.
2. CLI commands parse arguments with rich-click, delegate to `Registry` methods.
3. `resolve_key()` normalizes forward slashes to backslashes, parses hive
   names, and returns (hive_int, sub_key) tuples.
4. `Registry` methods manage cached connections/handles and delegate to
   `winreg` API functions.
5. On non-Windows, `fake_winreg` provides an in-memory simulated registry.

**System Dependencies:**
* `winreg` (stdlib, Windows only) or `fake_winreg` (PyPI, non-Windows)
* `rich_click` for CLI UX
* `rich` for enhanced tracebacks, console output, and table rendering

---

## Core Components

### registry.Registry

* **Purpose:** High-level Windows registry accessor with connection caching,
  handle management, and context manager with proper cleanup.
* **Key features:**
  - Connection caching by hive
  - Key handle caching by (hive, subkey, access) tuple
  - `close_all()` closes all cached handles (called by `__exit__` and `__call__`)
  - Automatic value type inference in `set_value()`
  - Recursive key creation/deletion
  - Remote computer support
  - SID enumeration and username resolution
  - Save/load subtrees to/from files
  - WOW64 reflection control
  - `delete_key_ex` cleans all cached access masks for the deleted key
* **Location:** src/lib_registry/registry.py

### Exception Hierarchy

* **Purpose:** Typed exceptions for specific registry failure modes.
* **Base:** `RegistryError`
* **Key subclasses:** `RegistryKeyNotFoundError`, `RegistryKeyCreateError`,
  `RegistryKeyDeleteError`, `RegistryValueNotFoundError`,
  `RegistryValueWriteError` (chains root cause via `from exc`),
  `RegistryHKeyError`, `RegistryNetworkConnectionError`
* **Location:** src/lib_registry/exceptions.py

### Helper Functions

* `normalize_separators()` - Convert `/` to `\` for cross-platform key paths
* `resolve_key()` - Parse key string/int into a `ResolvedKey(hive_key, sub_key)`
* `get_hkey_int()` - Extract HKEY constant from key name string
* `get_key_as_string()` - Format key as human-readable string
* `get_value_type_as_string()` - Format registry type as string
* `strip_backslashes()` - Strip leading/trailing backslashes
* `get_first_part_of_the_key()` - Extract first path component
* `remove_hive_from_key_str_if_present()` - Strip hive prefix
* **Location:** src/lib_registry/_helpers.py

### Named Constants

* `_WINERROR_FILE_NOT_FOUND`, `_WINERROR_ACCESS_DENIED`,
  `_WINERROR_INVALID_HANDLE`, `_WINERROR_NETWORK_PATH_NOT_FOUND`,
  `_WINERROR_NO_MORE_DATA`, `_WINERROR_KEY_MARKED_FOR_DELETION`,
  `_WINERROR_NETWORK_ADDRESS_INVALID` - replace magic numbers in error handling
  (src/lib_registry/_winreg_setup.py)

### Type Alias

* `RegData = None | bytes | int | str | list[str]` - Union of valid registry
  value types.

### Records (records.py)

`NamedTuple` records returned in place of bare tuples; each still unpacks and
compares like the tuple `winreg` returns.

* `ResolvedKey(hive_key, sub_key)` - from `resolve_key()`
* `KeyInfo(number_of_subkeys, number_of_values, last_modified_win_timestamp)` - from `key_info()`
* `TypedValue(data, reg_type)` - from `get_value_ex()`
* `RegValue(name, data, reg_type)` - yielded by `values()`

### Exported Constants

* All `HKEY_*` hive constants (7 hives with short aliases)
* All `REG_*` type constants (12 types)
* All `KEY_*` access constants (12 constants including WOW64)
* `l_hive_names` - `frozenset` for O(1) hive name lookups
* Lookup tables, read-only `MappingProxyType` views: `main_key_hashed_by_name`,
  `hive_names_hashed_by_int`, `reg_type_names_hashed_by_int`

### CLI Commands

All commands are defined in `src/lib_registry/cli.py` and delegate to
`Registry` methods. Forward slashes are accepted in all key paths.

| Command                       | Purpose                                                     |
|-------------------------------|-------------------------------------------------------------|
| `info`                        | Print package metadata                                      |
| `get KEY VALUE_NAME`          | Read and print a registry value (`--type` shows REG_* type) |
| `set KEY VALUE_NAME DATA`     | Write a value (REG_SZ by default; `--type` for other types) |
| `delete-value KEY VALUE_NAME` | Delete a value                                              |
| `list KEY`                    | List subkeys and values (`--keys`, `--values` filters)      |
| `exists KEY`                  | Check if key exists (exit code 0/1 for shell scripting)     |
| `create-key KEY`              | Create a key (`--parents` for intermediates)                |
| `delete-key KEY`              | Delete a key (`--recursive` for subtrees)                   |
| `export KEY FILE`             | Save key subtree to JSON file                               |
| `import KEY SUB_KEY FILE`     | Load key subtree from JSON file                             |
| `search KEY`                  | Recursive search by `--name` or `--data` glob patterns      |
| `users`                       | List SIDs with resolved usernames (rich table output)       |
| `sid SID`                     | Resolve a SID to a username                                 |
| `whoami USERNAME`             | Resolve a username to its SID                               |
| `tree KEY`                    | Show the key hierarchy (`--depth`, default 3)               |
| `copy SRC_KEY DST_KEY`        | Copy values, with `--recursive` the whole subtree           |
| `rename KEY OLD NEW`          | Rename a value (copy, then delete the old name)             |
| `diff KEY_A KEY_B`            | Compare two subtrees recursively                            |

Global options: `--json` (JSON output for `get`, `list`, `search`, `users`,
`sid`, `whoami`, `tree`, `diff`), `--quiet` (silences the confirmation lines of
`copy` and `rename`), `--computer` (remote registry) and
`--traceback/--no-traceback`.

**CLI `set` behavior:** Without `--type`, data is always stored as `REG_SZ`
(string). Use `--type REG_DWORD` explicitly for integers. With `--type`,
integer parsing accepts decimal, hex (`0xFF`), and octal (`0o77`), with
range validation for REG_DWORD (0..4294967295) and REG_QWORD (0..2**64-1).

### cli.main

* **Purpose:** Entry point for console scripts and module execution.
* **Input:** Optional argv sequence (defaults to sys.argv[1:]).
* **Output:** Integer exit code.
* **Location:** src/lib_registry/cli.py

### __init__conf__.print_info

* **Purpose:** Render statically-defined project metadata for the CLI
  `info` command.
* **Location:** src/lib_registry/__init__conf__.py

### Package Exports

* `__init__.py` re-exports the full Registry API, exception hierarchy,
  helper functions, `normalize_separators`, constants, and `print_info`
  via explicit `__all__`.

---

## Implementation Details

**Dependencies:**

* External: `winreg`/`fake_winreg`, `rich_click` (and the `rich` it brings)
* Internal: `__init__conf__` static metadata constants

**Key Configuration:**

* No environment variables required for registry operations.
* Traceback preferences controlled via CLI `--traceback` flag.
* On non-Windows, `fake_winreg` loads a minimal test registry at import time.

**Error Handling Strategy:**

* Typed exception hierarchy maps winreg OS errors to semantic exceptions.
* Named `_WINERROR_*` constants replace magic numbers for readability.
* `set_value` chains root cause exceptions via `from exc`.
* `from None` suppresses implicit exception chaining in `_reg_connect`.
* Rich tracebacks installed by default; `--no-traceback` suppresses them.
* CLI `users` catches `RegistryError` (not bare `Exception`) for SID resolution.

**Resource Management:**

* `__exit__` calls `close_all()` to close all cached handles and connections.
* `__call__` calls `close_all()` before re-initializing to prevent leaks.
* `delete_key_ex` iterates all cached access masks for the deleted key.
* `delete_key(..., delete_subkeys=True)` lists a key's children before deleting
  them: `RegEnumKey` enumerates by index, so deleting while enumerating would
  skip every other child.
* The CLI's recursive walkers (`list -r`, `search`, `tree`, `diff`, `copy -r`)
  close the handles they open for a key once they leave it
  (`_cli_helpers.released_handles`), so a walk holds one handle per level of
  depth. Every `--json` output of these commands is written while it is read
  (`_cli_helpers.echo_json`): `list` and `tree` describe their document with
  `JsonStream` arrays that read the registry only as they are written, and
  `search` and `diff` stream their results the same way. The output is the same
  text `json.dumps(..., indent=2)` would print, and memory stays bounded by the
  depth and the width of one key, not by the size of the subtree.

---

## Testing Approach

**Manual Testing Steps:**

1. `lib_registry info` - prints package metadata.
2. `lib_registry get "HKLM/SOFTWARE/Microsoft/Windows NT/CurrentVersion" CurrentBuild` - reads a value.
3. `lib_registry exists HKLM/SOFTWARE` - exit code 0 (exists).
4. `lib_registry list HKEY_USERS` - lists subkeys and values.
5. `lib_registry users` - lists SIDs with usernames.
6. `python -m lib_registry info` - matches console script behavior.

**Automated Tests:**

* `tests/test_cli.py` - the CLI commands, including forward-slash paths,
  error cases (missing values, overflow, invalid types) and round-trip
  create/set/get/delete/export/import. Uses `temp_key` and `temp_file` pytest
  fixtures for guaranteed teardown cleanup.
* `tests/test_walks.py` - the recursive walkers and the streaming JSON writer:
  output identical to `json.dumps`, handles released per level, the registry
  read only while the output is written.
* `tests/test_remote.py` - every operation on a `--computer` registry goes
  through the remote connection.
* `tests/test_packaging.py` - the sdist allowlist and the wheel's package data.
* `tests/test_platform_markers.py` - the `os_*` markers skip tests off their
  platform.
* `tests/test_module_entry.py` ensures `python -m` entry mirrors the console
  script.
* `tests/test_metadata.py` validates that `__init__conf__` constants match
  `pyproject.toml` using Pydantic models.
* Doctests in `registry.py` cover all public methods including key CRUD,
  value operations, SID enumeration, save/load, and error paths.

---

## Known Issues & Future Improvements

**Current Limitations:**

* `registry.py`, `cli.py`, `_cli_helpers.py`, `_helpers.py`, `_winreg_setup.py`
  and `tests/test_cli.py` are excluded from pyright strict checking. Checked
  strict, they report errors (most are the re-export imports in `registry.py`,
  the rest private-name use and partially unknown types), so the exclusion
  hides real findings rather than a missing stub.
* Coverage threshold at 70% due to Windows-only error handling branches.
* `save_key(key, file_name, sub_key="")` and `load_key(key, sub_key, file_name)` order their
  parameters differently on purpose: saving defaults to the key itself, loading always
  needs the target subkey.

**Future Enhancements:**

* Fix the strict pyright findings above and drop the exclusions.
* Give `info`, `copy` and `rename` a `--json` output.

---

**Review Cycle:** Evaluate when CLI commands or Registry methods change
