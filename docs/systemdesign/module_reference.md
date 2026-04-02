# Module Reference: lib_registry

## Status

Complete

## Links & References
**Repository:** https://github.com/bitranox/lib_registry
**Related Files:**

* src/lib_registry/registry.py
* src/lib_registry/cli.py
* src/lib_registry/__main__.py
* src/lib_registry/__init__.py
* src/lib_registry/__init__conf__.py
* tests/test_cli.py
* tests/test_module_entry.py
* tests/test_metadata.py

---

## Problem Statement

Python's built-in `winreg` module provides low-level access to the Windows
registry but requires manual handle management, verbose error handling, and
platform-specific code. `lib_registry` wraps `winreg` (and `fake_winreg` on
non-Windows platforms) with a high-level `Registry` class that provides
connection caching, automatic type detection, recursive operations, and a
cross-platform development experience.

## Solution Overview

* `registry.py` contains the `Registry` class, exception hierarchy, helper
  functions (including `normalize_separators` for forward-slash support),
  type aliases, named winerror constants, and all winreg constant re-exports.
* `cli.py` provides a rich-click CLI adapter with 12 commands for registry
  operations, delegating to `Registry` methods.
* `__main__.py` delegates to `cli.main()` for `python -m` execution.
* `__init__.py` re-exports the public API for library consumers.
* `__init__conf__.py` holds static metadata constants synced from
  `pyproject.toml` by automation.

---

## Architecture Integration

**Layer Structure:**
```
CLI adapter (cli.py, __main__.py)
        |
        v
Domain (registry.py)
        |
        v
winreg / fake_winreg
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
* **Location:** src/lib_registry/registry.py

### Helper Functions

* `normalize_separators()` - Convert `/` to `\` for cross-platform key paths
* `resolve_key()` - Parse key string/int into (hive_key, sub_key) tuple
* `get_hkey_int()` - Extract HKEY constant from key name string
* `get_key_as_string()` - Format key as human-readable string
* `get_value_type_as_string()` - Format registry type as string
* `strip_backslashes()` - Strip leading/trailing backslashes
* `get_first_part_of_the_key()` - Extract first path component
* `remove_hive_from_key_str_if_present()` - Strip hive prefix

### Named Constants

* `_WINERROR_FILE_NOT_FOUND`, `_WINERROR_ACCESS_DENIED`,
  `_WINERROR_INVALID_HANDLE`, `_WINERROR_NETWORK_PATH_NOT_FOUND`,
  `_WINERROR_NO_MORE_DATA`, `_WINERROR_KEY_MARKED_FOR_DELETION`,
  `_WINERROR_NETWORK_ADDRESS_INVALID` — replace magic numbers in error handling

### Type Alias

* `RegData = None | bytes | int | str | list[str]` - Union of valid registry
  value types.

### Exported Constants

* All `HKEY_*` hive constants (7 hives with short aliases)
* All `REG_*` type constants (12 types)
* All `KEY_*` access constants (12 constants including WOW64)
* `l_hive_names` — `frozenset` for O(1) hive name lookups
* Lookup dicts: `main_key_hashed_by_name`, `hive_names_hashed_by_int`,
  `reg_type_names_hashed_by_int`

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

**CLI `set` behavior:** Without `--type`, data is always stored as `REG_SZ`
(string). Use `--type REG_DWORD` explicitly for integers. With `--type`,
integer parsing accepts decimal, hex (`0xFF`), and octal (`0o77`), with
overflow validation for REG_DWORD (0..4294967295).

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

* External: `winreg`/`fake_winreg`, `rich_click`, `rich`
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

* `tests/test_cli.py` — 30+ tests covering all 12 CLI commands including
  forward-slash paths, error cases (missing values, overflow, invalid types),
  and round-trip create/set/get/delete/export/import. Uses `temp_key` and
  `temp_file` pytest fixtures for guaranteed teardown cleanup.
* `tests/test_module_entry.py` ensures `python -m` entry mirrors the console
  script.
* `tests/test_metadata.py` validates that `__init__conf__` constants match
  `pyproject.toml` using Pydantic models.
* Doctests in `registry.py` cover all public methods including key CRUD,
  value operations, SID enumeration, save/load, and error paths.

---

## Known Issues & Future Improvements

**Current Limitations:**

* `registry.py` and `cli.py` are excluded from pyright strict checking because
  `fake_winreg` lacks type stubs.
* Coverage threshold at 70% due to Windows-only error handling branches.
* `save_key` / `load_key` parameter order is asymmetric (intentional — see
  CLAUDE.md Code Quality section).

**Future Enhancements:**

* Add type stubs for fake_winreg to enable strict type checking.
* Add `--json` output flag to `list`, `search`, `users` for scripting.
* Add `--recursive` flag to `list --keys` for tree traversal.
* Add `--force` flag for destructive operations.

---

**Created:** 2025-09-26 by Codex (automation)
**Last Updated:** 2026-04-02 by Claude Code
**Review Cycle:** Evaluate when CLI commands or Registry methods change
