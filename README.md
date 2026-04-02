# lib_registry

<!-- Badges -->
[![CI](https://github.com/bitranox/lib_registry/actions/workflows/default_cicd_public.yml/badge.svg)](https://github.com/bitranox/lib_registry/actions/workflows/default_cicd_public.yml)
[![CodeQL](https://github.com/bitranox/lib_registry/actions/workflows/codeql.yml/badge.svg)](https://github.com/bitranox/lib_registry/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Open in Codespaces](https://img.shields.io/badge/Codespaces-Open-blue?logo=github&logoColor=white&style=flat-square)](https://codespaces.new/bitranox/lib_registry?quickstart=1)
[![PyPI](https://img.shields.io/pypi/v/lib_registry.svg)](https://pypi.org/project/lib_registry/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/lib_registry.svg)](https://pypi.org/project/lib_registry/)
[![Code Style: Ruff](https://img.shields.io/badge/Code%20Style-Ruff-46A3FF?logo=ruff&labelColor=000)](https://docs.astral.sh/ruff/)
[![codecov](https://codecov.io/gh/bitranox/lib_registry/graph/badge.svg?token=UFBaUDIgRk)](https://codecov.io/gh/bitranox/lib_registry)
[![Maintainability](https://qlty.sh/badges/041ba2c1-37d6-40bb-85a0-ec5a8a0aca0c/maintainability.svg)](https://qlty.sh/gh/bitranox/projects/lib_registry)
[![Known Vulnerabilities](https://snyk.io/test/github/bitranox/lib_registry/badge.svg)](https://snyk.io/test/github/bitranox/lib_registry)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)


A more pythonic way to access the Windows registry as winreg.

Wraps Python's `winreg` module with a high-level `Registry` class providing
connection caching, automatic type detection, recursive key operations, and
a context manager. On non-Windows platforms, `fake_winreg` provides a
simulated registry so tests and code run everywhere.

## Features

- Pythonic `Registry` class with context manager support
- Automatic registry value type detection (str, int, bytes, list)
- Connection and key handle caching for performance
- Recursive key creation (`parents=True`) and deletion (`delete_subkeys=True`)
- Remote computer registry access
- SID enumeration and username resolution
- Save/load registry subtrees to/from files
- WOW64 32/64-bit registry view support
- Registry reflection control
- Cross-platform via `fake_winreg` on Linux/macOS
- CLI entry point with rich-click styling

## Install

```bash
pip install lib_registry
```

Or with [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv pip install lib_registry
```

For all installation methods (pipx, uvx, poetry, etc.), see [INSTALL.md](INSTALL.md).

### Python 3.9+ Baseline

- Targets **Python 3.9 and newer**
- Runtime dependencies: `rich-click` for CLI output, `rtoml` for TOML parsing,
  `fake_winreg` on non-Windows platforms
- CI covers CPython 3.9 through 3.14

## Usage

### As a library

```python
import lib_registry

# Create a registry accessor
registry = lib_registry.Registry()

# Check if a key exists
registry.key_exist('HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion')

# Read a value
build = registry.get_value(
    'HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion',
    'CurrentBuild',
)

# Create a key and write values
registry.create_key('HKCU\\Software\\MyApp', parents=True)
registry.set_value('HKCU\\Software\\MyApp', 'Setting', 'value')
registry.set_value('HKCU\\Software\\MyApp', 'Count', 42)

# Iterate subkeys and values
for subkey in registry.subkeys('HKEY_USERS'):
    print(subkey)

for name, data, reg_type in registry.values('HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion'):
    print(f'{name} = {data}')

# Save and load registry subtrees
registry.save_key('HKCU\\Software\\MyApp', '/tmp/myapp_backup.json')
registry.load_key(lib_registry.winreg.HKEY_CURRENT_USER, 'Software\\MyAppCopy', '/tmp/myapp_backup.json')

# Clean up
registry.delete_key('HKCU\\Software\\MyApp', delete_subkeys=True)

# Use as context manager
with lib_registry.Registry('HKLM') as reg:
    info = reg.key_info('HKLM\\SOFTWARE')
```

### Path separators

Both backslashes and forward slashes are accepted in registry paths:

```python
# These are equivalent:
registry.key_exist('HKLM\\SOFTWARE\\Microsoft')
registry.key_exist('HKLM/SOFTWARE/Microsoft')
```

### CLI Reference

All commands accept registry paths with either backslashes (`\`) or forward
slashes (`/`). Hive names are case-insensitive (`HKLM`, `hklm`,
`HKEY_LOCAL_MACHINE` all work). Run any command with `-h` for built-in help.

#### Global options

```
lib_registry [OPTIONS] COMMAND [ARGS]...
```

| Option                       | Default | Description                          |
|------------------------------|---------|--------------------------------------|
| `--version`                  |         | Print version and exit               |
| `--traceback/--no-traceback` | on      | Show full Python traceback on errors |
| `-q, --quiet`                | off     | Suppress non-error output            |
| `--json`                     | off     | Emit JSON output (for scripting)     |
| `--computer HOST`            |         | Connect to remote computer registry  |
| `-h, --help`                 |         | Show help and exit                   |

Also available as `python -m lib_registry`.

---

#### `info` -- package metadata

```bash
lib_registry info
```

Print resolved package metadata (name, version, homepage, author).

---

#### `get` -- read a value

```bash
lib_registry get [OPTIONS] KEY VALUE_NAME
```

| Argument/Option | Required | Description                                    |
|-----------------|----------|------------------------------------------------|
| `KEY`           | yes      | Registry key path (e.g. `HKLM/SOFTWARE/...`)   |
| `VALUE_NAME`    | yes      | Name of the value to read (omit for default)   |
| `--type`        | no       | Also display the REG_* type alongside the data |
| `--default`     | no       | Read the unnamed default value                 |

**Examples:**

```bash
lib_registry get "HKLM/SOFTWARE/Microsoft/Windows NT/CurrentVersion" CurrentBuild
# Output: 19045

lib_registry get --type "HKLM/SOFTWARE/Microsoft/Windows NT/CurrentVersion" CurrentBuild
# Output: REG_SZ: 19045
```

---

#### `set` -- write a value

```bash
lib_registry set [OPTIONS] KEY VALUE_NAME DATA
```

| Argument/Option | Required | Description                                                                                                                                                                                                                              |
|-----------------|----------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `KEY`           | yes      | Registry key path                                                                                                                                                                                                                        |
| `VALUE_NAME`    | yes      | Name of the value to write                                                                                                                                                                                                               |
| `DATA`          | yes      | Value data as string (converted based on `--type`)                                                                                                                                                                                       |
| `--type TYPE`   | no       | Registry type. One of: `REG_SZ`, `REG_DWORD`, `REG_QWORD`, `REG_BINARY`, `REG_MULTI_SZ`, `REG_EXPAND_SZ`, `REG_NONE`, etc. Without `--type`, data is always stored as `REG_SZ` (string). Use `--type REG_DWORD` explicitly for integers. |
| `--default`     | no       | Write the unnamed default value (VALUE_NAME ignored)                                                                                                                                                                                     |

**Type conversion rules:**

| `--type`       | DATA is parsed as          | Example                           |
|----------------|----------------------------|-----------------------------------|
| *(omitted)*    | always string (REG_SZ)     | `42` -> REG_SZ, `hello` -> REG_SZ |
| `REG_SZ`       | string                     | `"hello world"`                   |
| `REG_DWORD`    | integer (32-bit)           | `42`                              |
| `REG_QWORD`    | integer (64-bit)           | `9999999999`                      |
| `REG_BINARY`   | UTF-8 encoded bytes        | `"raw data"`                      |
| `REG_MULTI_SZ` | `\0`-delimited string list | `"line1\0line2\0line3"`           |
| `REG_NONE`     | None (empty)               | *(DATA ignored)*                  |

**Examples:**

```bash
lib_registry set HKCU/Software/MyApp Setting "hello world"
lib_registry set HKCU/Software/MyApp Count 42 --type REG_DWORD
lib_registry set HKCU/Software/MyApp Paths "C:\bin\0D:\tools" --type REG_MULTI_SZ
```

Silent on success (exit code 0).

---

#### `delete-value` -- remove a value

```bash
lib_registry delete-value KEY VALUE_NAME
```

| Argument/Option | Required | Description                            |
|-----------------|----------|----------------------------------------|
| `KEY`           | yes      | Registry key path                      |
| `VALUE_NAME`    | yes      | Name of the value to delete            |
| `--force`       | no       | Suppress error if value does not exist |

Silent on success.

---

#### `list` -- list subkeys and values

```bash
lib_registry list [OPTIONS] KEY
```

| Argument/Option   | Required | Description          |
|-------------------|----------|----------------------|
| `KEY`             | yes      | Registry key path    |
| `--keys`          | no       | Show subkeys only    |
| `--values`        | no       | Show values only     |
| `--recursive, -r` | no       | Recurse into subkeys |

Without flags, shows both subkeys and values. Output format:

```
[KEY] SubkeyName
[REG_SZ] ValueName = data
[REG_DWORD] Count = 42
```

**Examples:**

```bash
lib_registry list HKEY_USERS
lib_registry list --keys HKEY_USERS
lib_registry list --values "HKLM/SOFTWARE/Microsoft/Windows NT/CurrentVersion"
```

---

#### `exists` -- check key existence

```bash
lib_registry exists KEY
```

| Argument | Required | Description       |
|----------|----------|-------------------|
| `KEY`    | yes      | Registry key path |

Produces no output. Exit code **0** if the key exists, **1** if it does not.
Designed for shell scripting:

```bash
if lib_registry exists HKCU/Software/MyApp; then
    echo "Key exists"
fi
```

---

#### `create-key` -- create a registry key

```bash
lib_registry create-key [OPTIONS] KEY
```

| Argument/Option | Required | Description                                |
|-----------------|----------|--------------------------------------------|
| `KEY`           | yes      | Registry key path to create                |
| `--parents`     | no       | Create intermediate parent keys if missing |

Silent on success. Without `--parents`, fails if the parent key does not exist.

**Examples:**

```bash
lib_registry create-key HKCU/Software/MyApp
lib_registry create-key HKCU/Software/MyApp/Deep/Nested/Key --parents
```

---

#### `delete-key` -- delete a registry key

```bash
lib_registry delete-key [OPTIONS] KEY
```

| Argument/Option | Required | Description                                          |
|-----------------|----------|------------------------------------------------------|
| `KEY`           | yes      | Registry key path to delete                          |
| `--recursive`   | no       | Also delete all subkeys and their values recursively |
| `--force`       | no       | Suppress error if key does not exist                 |

Silent on success. Without `--recursive`, fails if the key has subkeys.

**Examples:**

```bash
lib_registry delete-key HKCU/Software/MyApp
lib_registry delete-key HKCU/Software/MyApp --recursive
```

---

#### `export` -- save a key subtree to file

```bash
lib_registry export KEY FILE
```

| Argument | Required | Description                    |
|----------|----------|--------------------------------|
| `KEY`    | yes      | Registry key path to export    |
| `FILE`   | yes      | Output file path (JSON format) |

Saves the key and all its subkeys/values to a JSON file. Use `import`
to restore.

```bash
lib_registry export HKCU/Software/MyApp backup.json
```

---

#### `import` -- load a key subtree from file

```bash
lib_registry import KEY SUB_KEY FILE
```

| Argument  | Required | Description                                     |
|-----------|----------|-------------------------------------------------|
| `KEY`     | yes      | Hive or parent key (e.g. `HKCU`)                |
| `SUB_KEY` | yes      | Subkey path under KEY where data will be loaded |
| `FILE`    | yes      | Input file path (JSON, as produced by `export`) |

```bash
lib_registry import HKCU Software/MyAppCopy backup.json
```

---

#### `search` -- find values by pattern

```bash
lib_registry search [OPTIONS] KEY
```

| Argument/Option  | Required | Description                                             |
|------------------|----------|---------------------------------------------------------|
| `KEY`            | yes      | Registry key path to search under (recursive)           |
| `--name PATTERN` | no       | Glob pattern to match value names (e.g. `"Install*"`)   |
| `--data PATTERN` | no       | Glob pattern to match value data (e.g. `"*Microsoft*"`) |

Recursively walks all subkeys under KEY and prints matching values.
At least one of `--name` or `--data` should be specified.

**Output format:**

```
HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion  [REG_SZ] CurrentBuild = 19045
```

**Examples:**

```bash
lib_registry search "HKLM/SOFTWARE/Microsoft/Windows NT/CurrentVersion" --name "Current*"
lib_registry search HKLM/SOFTWARE --data "*Python*"
```

---

#### `users` -- list Windows users from registry

```bash
lib_registry users
```

No arguments. Enumerates SIDs from the ProfileList and resolves usernames.
Output is a formatted table:

```
      Registry Users
+-----------------------+----------+
| SID                   | Username |
+-----------------------+----------+
| S-1-5-21-...-1000     | alice    |
| S-1-5-18              | SYSTEM   |
+-----------------------+----------+
```

---

#### `tree` -- visual key hierarchy

```bash
lib_registry tree [OPTIONS] KEY
```

| Argument/Option | Required | Description                           |
|-----------------|----------|---------------------------------------|
| `KEY`           | yes      | Registry key path                     |
| `--depth N`     | no       | Maximum depth to display (default: 3) |

Displays a Rich tree view of the key hierarchy. With `--json`, outputs a
nested dict.

```bash
lib_registry tree HKEY_USERS --depth 2
lib_registry --json tree HKLM/SOFTWARE --depth 1
```

---

#### `copy` -- copy a key

```bash
lib_registry copy [OPTIONS] SRC_KEY DST_KEY
```

| Argument/Option | Required | Description                              |
|-----------------|----------|------------------------------------------|
| `SRC_KEY`       | yes      | Source key path                          |
| `DST_KEY`       | yes      | Destination key path (created if needed) |
| `--recursive`   | no       | Also copy all subkeys recursively        |

Copies all values from SRC_KEY to DST_KEY. With `--recursive`, copies the
entire subtree.

```bash
lib_registry copy HKCU/Software/MyApp HKCU/Software/MyAppBackup --recursive
```

---

#### `rename` -- rename a value

```bash
lib_registry rename KEY OLD_NAME NEW_NAME
```

| Argument   | Required | Description        |
|------------|----------|--------------------|
| `KEY`      | yes      | Registry key path  |
| `OLD_NAME` | yes      | Current value name |
| `NEW_NAME` | yes      | New value name     |

Renames a registry value by copying its data and type to the new name, then
deleting the old name. Atomic within a single key.

```bash
lib_registry rename HKCU/Software/MyApp OldSetting NewSetting
```

---

#### `diff` -- compare two keys

```bash
lib_registry diff KEY_A KEY_B
```

| Argument | Required | Description                |
|----------|----------|----------------------------|
| `KEY_A`  | yes      | First key path to compare  |
| `KEY_B`  | yes      | Second key path to compare |

Recursively compares values and subkeys between two registry key subtrees.
Shows values only in A, only in B, and values that differ.

```bash
lib_registry diff HKCU/Software/MyApp HKCU/Software/MyAppBackup
lib_registry --json diff HKCU/Software/V1 HKCU/Software/V2
```

Output format:
```
  - HKCU\Software\MyApp  (only in KEY_A)
  + HKCU\Software\MyAppBackup  (only in KEY_B)
  ~ HKCU\Software\MyApp / Setting
    A: old_value
    B: new_value
```

---

### Access constants

All `winreg` KEY_* access constants are re-exported for convenience:

```python
from lib_registry import KEY_READ, KEY_WRITE, KEY_ALL_ACCESS, KEY_WOW64_64KEY
```

## API Overview

### Registry class methods

| Method                         | Description                                                   |
|--------------------------------|---------------------------------------------------------------|
| `create_key()`                 | Create a registry key (with `parents` and `exist_ok` options) |
| `create_key_ex()`              | Create with explicit access mask                              |
| `delete_key()`                 | Delete a key (with `delete_subkeys` and `missing_ok` options) |
| `delete_key_ex()`              | Delete with WOW64 view control                                |
| `key_exist()`                  | Check whether a key exists                                    |
| `key_info()`                   | Get metadata (subkey count, value count, last modified)       |
| `number_of_subkeys()`          | Count subkeys                                                 |
| `number_of_values()`           | Count values                                                  |
| `has_subkeys()`                | Check if key has children                                     |
| `subkeys()`                    | Iterate over subkey names                                     |
| `values()`                     | Iterate over (name, data, type) tuples                        |
| `get_value()`                  | Read a value's data                                           |
| `get_value_ex()`               | Read a value's data and type                                  |
| `set_value()`                  | Write a value (auto-detects type)                             |
| `delete_value()`               | Delete a value                                                |
| `flush_key()`                  | Force registry writes to disk                                 |
| `save_key()`                   | Save key subtree to file                                      |
| `load_key()`                   | Load key subtree from file                                    |
| `close_key()`                  | Explicitly close a cached handle                              |
| `sids()`                       | Iterate over Windows Security Identifiers                     |
| `username_from_sid()`          | Resolve username from SID                                     |
| `last_access_timestamp()`      | Last-modified as Unix timestamp                               |
| `disable_reflection_key()`     | Disable WOW64 reflection                                      |
| `enable_reflection_key()`      | Re-enable WOW64 reflection                                    |
| `query_reflection_key()`       | Check reflection state                                        |
| `expand_environment_strings()` | Expand `%VAR%` references (static method)                     |

### Exception hierarchy

```
RegistryError
  RegistryConnectionError
  RegistryKeyError
    RegistryKeyNotFoundError
    RegistryKeyExistsError
    RegistryKeyCreateError
    RegistryKeyDeleteError
  RegistryValueError
    RegistryValueNotFoundError
    RegistryValueDeleteError
    RegistryValueWriteError
  RegistryHKeyError
  RegistryNetworkConnectionError
  RegistryHandleInvalidError
```


## Further Documentation

- [Install Guide](INSTALL.md)
- [Development Handbook](DEVELOPMENT.md)
- [Contributor Guide](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [Module Reference](docs/systemdesign/module_reference.md)
- [License](LICENSE)
