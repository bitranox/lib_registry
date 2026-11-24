# Changelog

All notable changes to this project will be documented in this file following
the [Keep a Changelog](https://keepachangelog.com/) format.

## [Unreleased]

### Changed

- Every module is now type-checked by pyright in strict mode; the exclusions for `registry.py`,
  `cli.py`, `_cli_helpers.py`, `_helpers.py`, `_winreg_setup.py` and `tests/test_cli.py` are gone.
- `lib_registry.registry.__all__` now lists every name the module defined before the 3.1.1 split
  (constants, helpers, exceptions, `winreg`), which it already re-exported, so
  `from lib_registry.registry import *` gives the same names as in 3.0.
- The private `_WINERROR_*` constants in `lib_registry._winreg_setup` are named `WINERROR_*`.
- The Windows error code of a failed registry call is read through one typed accessor,
  `winerror_of`, instead of `hasattr` plus a direct `.winerror` read that needed a type-checker
  suppression on every platform but Windows. Every `# type: ignore` comment is gone, and pyright
  is configured to ignore any new one (`enableTypeIgnoreComments = false`): under pyright a
  mypy-style `# type: ignore[code]` silences the whole line, so it could hide unrelated errors.

### Tests

- The connection errors `Registry` reports for each Windows error code (network path not found,
  invalid network address, invalid handle, none) are now tested on every platform.

## [3.3.2] - 2026-11-24

### Fixed

- `set --type REG_QWORD` now refuses a value outside 0 to 2**64-1 with exit code 2 before
  writing, as `REG_DWORD` already did for its range. Before, such a value reached `winreg`, which
  refuses it on Windows with a traceback, while `fake_winreg` stored it.
- `tree --json` named the root after the whole key when the path used forward slashes
  (`"name": "HKCU/Software/MyApp"`) and after its last part with backslashes (`"MyApp"`). Both
  spellings now give the last part.

### Changed

- `rtoml` is no longer a runtime dependency; nothing in the package imported it.

### Documentation

- README: the CLI reference now says which commands `--json` and `--quiet` affect, that
  `get`'s VALUE_NAME is optional, the integer ranges and hex input of `set`, how `search` prints
  subkey paths, the output of `copy` and `rename` (which is not atomic and overwrites an existing
  NEW_NAME), and the fields of `diff --json`. Every exported helper and lookup table is listed.
- INSTALL.md, DEVELOPMENT.md and CONTRIBUTING.md rewritten for the bmk workflow; they described
  a Makefile, scripts and options this repository no longer has.
- The module reference lists every module and all 18 CLI commands.

## [3.3.1] - 2026-11-24

### Fixed

- `list --recursive --json` and `tree --json` built the whole subtree as one document in memory
  before printing it. They now print it while they walk, through the same streaming JSON writer
  `search` and `diff` use, with byte-identical output. Measured over 1,000 and 8,000 keys (warm
  runs, output to /dev/null): `list -r --json` peaked at 1,698 and 12,453 KiB before, 723 and
  739 KiB now; `tree --json` at 625 and 3,140 KiB before, 588 and 764 KiB now.

## [3.3.0] - 2026-11-24

### Changed

- `fake_winreg>=1.11.0` (runtime, non-Windows); `uv.lock` refreshed.
- The exported lookup tables `main_key_hashed_by_name`, `hive_names_hashed_by_int` and
  `reg_type_names_hashed_by_int` are now read-only `MappingProxyType` views, typed `Mapping`.
  Every key parse in a process reads them, so a caller writing an entry changed how every later
  key resolved. Reading, `in`, iteration, `.items()` and `dict(table)` work as before; item
  assignment, `.update()`, `json.dumps(table)` and pickling no longer do (use `dict(table)`).

### Fixed

- Remote registry access did not reach the remote computer. `Registry(computer_name="X")` (and the
  CLI's `--computer X`, which builds it that way) connected every hive to the LOCAL computer, so
  reads and writes silently went to the local registry. `Registry("HKLM", computer_name="X")`
  connected that one hive to X and then refused every further operation with
  `RegistryError: can not connect to different Machines in the same scope`. Every connection now
  goes to the computer the `Registry` was created for, and `create_key`, `delete_key` and
  `delete_key_ex` work through that computer's connection instead of the bare local hive constant.

## [3.2.0] - 2026-11-24

### Changed

- Dependency floors raised to the current releases: `fake_winreg>=1.10.5` (runtime, non-Windows),
  and in the dev extra `ruff>=0.17.5`, `click>=8.5.1` and `pydantic>=2.14.3`. `uv.lock` refreshed.

### Added

- `KeyInfo`, `TypedValue`, `RegValue` and `ResolvedKey`, `NamedTuple` records exported from the
  package. `key_info()` returns a `KeyInfo`, `get_value_ex()` a `TypedValue`, `values()` yields
  `RegValue` records and `resolve_key()` returns a `ResolvedKey`. Each still unpacks, indexes and
  compares like the plain tuple it replaces, so existing callers keep working; the fields can now
  also be read by name (`info.number_of_subkeys`, `value.reg_type`). Their `repr` shows the record
  name and field names.

### Fixed

- On Windows, a type checker saw every `winreg` type that `Registry` exposes (its handles, the
  `REG_*` constants) as unknown, because `_winreg_setup` chose between `winreg` and `fake_winreg`
  through a runtime flag and fake_winreg is not installed there. It now branches on
  `sys.platform == "win32"`, which type checkers narrow. `is_platform_windows` keeps its value.
- `Registry.delete_key(..., delete_subkeys=True)` failed with `PermissionError: [WinError 5]
  Access is denied` on a key with two or more children. It deleted the children while enumerating
  them by index, and every delete shifted the remaining children down one slot, so it skipped
  every other child and the final delete of the parent found it still had subkeys. It now lists the
  children first. `lib_registry delete-key --recursive` had the same failure.
- `lib_registry diff` printed a value present in only one key as just the key path
  (`- HKCU\Software\A  (only in ...)`), so the output did not say which value it meant. It now
  prints `- HKCU\Software\A / ValueName  (only in ...)`, like the line for a value that differs.
  The `--json` output is unchanged.
- The recursive CLI commands (`list --recursive`, `search`, `tree`, `diff`, `copy --recursive`) kept
  one open registry handle for every key they visited until the command ended, because `Registry`
  caches each handle it opens. Over a large subtree (all of `HKLM\SOFTWARE`) that is hundreds of
  thousands of open handles. They now close a key's handles when they leave it, so a walk holds one
  handle per level of depth. `search` and `diff` also yield their results one at a time and print
  their JSON arrays as they go instead of collecting the whole result first; the bytes printed are
  the same.
- `notebooks/Quickstart.ipynb` installs the checkout it runs in, so CI's "Execute notebooks" job
  tests the commit under test. It used to install `git+https://github.com/...` every time, which is
  the pushed default branch, so a pull request's notebook run tested the code already there.
  Outside a checkout (a downloaded notebook) it still installs from GitHub.

## [3.1.7] - 2026-10-21

### Fixed

- The CLI export/import tests and the `save_key`/`load_key` doctests wrote to fixed file names in
  the system temp dir (`_lib_reg_cli_test.json`, `_lib_reg_save_test.json`,
  `_lib_reg_load_test.json`). Two pytest runs at once, as `bmk test-all` starts one per Python
  version, overwrote or deleted each other's file and failed with exit code 2, a `JSONDecodeError`
  or a `FileNotFoundError`. The tests now write under `tmp_path` and the doctests under a
  `tempfile.TemporaryDirectory`, so every run gets its own file.

## [3.1.6] - 2026-10-15

### Fixed

- The source distribution ships only the package, its tests, its docs, `README.md`, `LICENSE`,
  `CHANGELOG.md` and `pyproject.toml` (an include list). Earlier sdists also carried every other
  root file and, in a local build, anything hidden only through `.git/info/exclude` or a nested
  `.gitignore`. `tests/test_packaging.py` builds the sdist and wheel and checks both; `hatchling`
  joins the dev extra for it.

### Changed

- Ruff selects `C90` (mccabe), so a function over cyclomatic complexity 10, the house hard limit,
  now fails `make test`; before, nothing enforced it.

### Tests

- The `os_windows`, `os_macos`, `os_linux` and `os_posix` markers now skip a test off its platform
  (`pytest_runtest_setup` in `tests/conftest.py`); registered in `pyproject.toml` alone they skipped
  nothing, so a test trusting its marker ran everywhere. `tests/test_platform_markers.py` pins it.

## [3.1.5] - 2026-10-13

### Added
- Python 3.15 is a supported version: declared in the classifiers, so CI and `make test-all` run it.
- `uv.lock` is committed, and `[tool.uv] exclude-newer` sets a cooldown that keeps releases younger
  than it out of the lock. CI installs exactly the locked tree on push and pull request; the nightly
  scheduled run still resolves afresh to catch upstream breakage early.

### Changed
- The install section explains why installing with uv protects against supply-chain attacks and why
  a plain `pip install` from PyPI does not.
- `rtoml` floor raised to 0.14.0, the first release with Python 3.15 wheels.

## [3.1.4] - 2026-07-24

### Changed
- Pinned the ruff lint policy with an explicit `[tool.ruff.lint].select` (the curated bitranox
  rule set) instead of relying on ruff's default, so a future ruff release widening its default
  rule set can no longer silently re-explode the violation count.
- Added per-file-ignores for `PLR0913` on `cli.py` and `_cli_helpers.py` (Click commands and their
  formatting helpers genuinely need more than 5 parameters).

### Fixed
- Made every CLI command callback's option parameters keyword-only (`PLR0917`/`FBT001`); Click
  already invokes callbacks by keyword, so this is not a behavior change.
- Made `list_human`/`list_to_dict` option parameters keyword-only and updated their call sites.
- Replaced `try/except/pass` around handle cleanup with `contextlib.suppress` (`SIM105`).
- Replaced manual `for`+`append` loops with `list.extend` (`PERF401`).
- Added `raise ... from None` to exceptions re-raised inside an `except` clause (`B904`).
- Replaced `os.path`/`os.remove` with `pathlib.Path` in `tests/test_cli.py` (`PTH107`/`PTH113`/`PTH118`).
- Replaced `print()` with `sys.stdout.write()` in `print_info()` (`T201`).
- Extracted the `0xFFFFFFFF` REG_DWORD bound into a named constant (`PLR2004`).
- Sorted `__all__` in `src/lib_registry/__init__.py` (`RUF022`).
- `Registry.create_key`/`delete_key` keep their existing positional-or-keyword boolean flags
  (`exist_ok`, `parents`, `missing_ok`, `delete_subkeys`) with a scoped `noqa: FBT001, FBT002`:
  they are public API, and making them keyword-only would break any caller passing them
  positionally.
- `Registry.subkeys`/`values` keep their per-iteration `try/except OSError` with a scoped
  `noqa: PERF203`: `winreg.EnumKey`/`EnumValue` signal end-of-enumeration via `OSError`, so the
  loop-local exception handling is the API's own contract, not an avoidable pattern.

## [3.1.3] - 2026-06-14

### Changed
- Added a `typed_click.py` facade wrapping rich-click's `option` / `argument` / `version_option` decorators behind explicit, fully-known signatures, keeping the CLI strict-clean under pyright 1.1.410 (`reportUnknownMemberType`) without disabling the rule (ignore isolated to the facade). `cli.py` remains in the pyright `exclude` list for non-click reasons (private-helper imports from excluded modules).
- Bumped `fake_winreg` floor to `>=1.9.1`.

## [3.1.2] - 2026-04-02

### Changed
- Comprehensive API Reference in README with full signatures, parameters, examples,
  and type mapping table for every public method

## [3.1.1] - 2026-04-02

### Changed
- Split `registry.py` (1624 lines) into 4 modules: `_winreg_setup.py` (constants),
  `exceptions.py` (exception hierarchy), `_helpers.py` (key parsing), `registry.py`
  (Registry class only)
- Split `cli.py` (689 lines) into 2 modules: `_cli_helpers.py` (formatting, tree,
  diff, copy helpers), `cli.py` (commands and entry point)
- Import-linter enforces 5-layer dependency direction:
  `cli -> _cli_helpers -> registry -> _helpers -> exceptions|_winreg_setup`
- All public API imports unchanged (backward compatible)

## [3.1.0] - 2026-04-02

### Added
- `sid_from_username()` method: reverse lookup from username to SID (case-insensitive)
- CLI `sid` command: resolve a SID to a username
- CLI `whoami` command: resolve a username to its SID (reverse lookup)
- Both new commands support `--json` output

### Fixed
- `username_from_sid('.DEFAULT')` now returns `"Default"` instead of raising
  `RegistryError` (fixes [#2](https://github.com/bitranox/lib_registry/issues/2))
- `sid_from_username('Default')` returns `".DEFAULT"` without iterating ProfileList

## [3.0.1] - 2026-04-02

### Changed
- Drop Python 3.9 support, require Python 3.10+
- Remove `from __future__ import annotations` from all modules (native 3.10+ syntax)
- Replace `typing.Union` with native `X | Y` union syntax for `RegData` type alias
- Replace `typing.Iterator` with `collections.abc.Iterator`
- Simplify all conditional dependency constraints (no more 3.9 forks)
- Ruff target updated from `py39` to `py310`

## [3.0.0] - 2026-04-02

### Added
- `Registry` class wrapping `winreg` with connection caching, handle management,
  and context manager with proper cleanup (`close_all()`)
- Full exception hierarchy: `RegistryError`, `RegistryKeyNotFoundError`,
  `RegistryValueNotFoundError`, `RegistryHKeyError`, etc.
- Key operations: `create_key`, `delete_key`, `key_exist`, `key_info`,
  `subkeys`, `has_subkeys`, `number_of_subkeys`
- Value operations: `get_value`, `get_value_ex`, `set_value`, `delete_value`,
  `values`, `number_of_values`
- Extended operations: `create_key_ex`, `delete_key_ex`, `flush_key`,
  `close_key`, `close_all`, `save_key`, `load_key`
- WOW64 reflection control: `disable_reflection_key`, `enable_reflection_key`,
  `query_reflection_key`
- Utility: `expand_environment_strings` (static method),
  `normalize_separators` (forward-slash to backslash conversion)
- SID support: `sids`, `username_from_sid`
- Timestamp methods: `last_access_timestamp`, `last_access_timestamp_windows`
- Helper functions: `resolve_key`, `get_hkey_int`, `get_key_as_string`,
  `get_value_type_as_string`, `strip_backslashes`
- All `KEY_*` access constants re-exported at module level
- `RegData` type alias for registry value types
- `fake_winreg>=1.9.0` dependency for cross-platform support
- Forward-slash path support: `HKLM/SOFTWARE/Microsoft` accepted everywhere
- Named constants for Windows error codes (`_WINERROR_*`)
- 16 CLI commands: `info`, `get`, `set`, `delete-value`, `list`, `exists`,
  `create-key`, `delete-key`, `export`, `import`, `search`, `users`,
  `tree`, `copy`, `rename`, `diff`
- CLI global flags: `--json` (JSON output), `-q/--quiet` (suppress output),
  `--computer HOST` (remote registry)
- CLI `get`/`set` support `--default` for unnamed default values
- CLI `delete-key`/`delete-value` support `--force` (suppress missing errors)
- CLI `list` supports `--recursive` for subtree traversal
- CLI `set` validates integer range for REG_DWORD and accepts hex (`0xFF`)
- CLI `exists` returns exit code 0/1 for shell scripting
- Comprehensive doctests for all public methods
- Pytest fixtures (`temp_key`, `temp_file`) with guaranteed teardown cleanup

### Changed
- Project description: "a more pythonic way to access the windows registry as winreg"
- `__exit__` now calls `close_all()` to close all cached handles (was empty)
- `__call__` now calls `close_all()` before re-initializing (was leaking handles)
- `delete_key_ex` now cleans all cached access masks, not just KEY_READ/KEY_ALL_ACCESS
- `set_value` exception now chains root cause via `from exc`
- `_infer_value_type` uses `value_type is None` instead of `not value_type`
  (fixes bug where REG_NONE=0 was treated as "not provided")
- `l_hive_names` changed from list to frozenset for O(1) membership tests
- CLI `set` without `--type` defaults to REG_SZ (string), not auto-detect int
- CLI `users` catches `RegistryError` instead of bare `Exception`
- CLI `exists` uses `raise SystemExit(1)` instead of `ctx.exit(1)`
- `load_key` normalizes `sub_key` with `normalize_separators()`
- Import-linter contract updated for registry module
- Coverage threshold adjusted to 70% (Windows-only error handling branches)

### Removed
- `behaviors.py` scaffold placeholder module (emit_greeting, raise_intentional_failure, noop_main)
- `hello` and `fail` CLI commands
- `test_behaviors.py` test file
- `WritableStream` protocol and `CANONICAL_GREETING` constant
- `bitranox-template-py-cli` stale console script entry point

## [1.1.1] - 2026-02-18

### Added
- `__all__` export declaration in `__init__conf__.py` for consistent public API surface

### Fixed
- Pin `rtoml` and `pip-audit` versions for Python 3.9 compatibility
- Ignore `filelock` transitive dependency vulnerabilities in pip-audit

## [1.1.0] - 2026-02-18

### Added
- `WritableStream` Protocol for narrower stream typing in `behaviors.py`
- `CliContext` dataclass replacing untyped dict for Click context storage
- Dynamic CI matrix extracting Python versions from pyproject.toml classifiers
- Pydantic models for typed TOML parsing in test suite
- Test covering `SystemExit` branch in `cli.main()` for 100% cli.py coverage
- `pydantic` added to dev dependencies

### Changed
- Replace `TextIO` with `WritableStream` Protocol for honest, minimal typing
- Rename `ERROR_STYLE` to `_ERROR_STYLE` (private convention)
- Replace `scripts/` Python build system with bmk-based Makefile targets
- CI workflows renamed and modernized (`default_cicd_public.yml`, `default_release_public.yml`)
- Use stdlib `tomllib` instead of `rtoml` in CI setup job
- Update dev dependency pins (pydantic, ruff, pyright, bandit, etc.)

### Fixed
- CI `IndexError` in Python version parsing by switching to stdlib `tomllib`
- Inconsistent spacing in pip-audit ignore-vulns list
- Undeclared `local_only` pytest marker

### Removed
- `scripts/` directory (replaced by bmk Makefile targets)
- `CLAUDE.md` project instructions file (moved to project-level config)

## [1.0.3] - 2025-12-15

### Changed
- Move deferred imports to module top in `cli.py` for better readability
- Modernize type hints: `Optional[X]` replaced with `X | None` syntax
- Use `collections.abc.Sequence` instead of `typing.Sequence`
- Extract `_exit_code_from()` helper function with comprehensive doctests
- Extract `_print_error()` helper function for cleaner error handling
- Add `ERROR_STYLE` module-level constant for error message styling
- Add typed context documentation comment for Click context dict

### Added
- Add `__all__` export list to `cli.py` for explicit public API surface

### Fixed
- Remove unused `strip_ansi` fixture parameter from test functions
- Remove unused `Callable` import from `test_cli.py`

## [1.0.2] - 2025-12-15

### Changed
- Update CI/CD workflows to use latest GitHub Actions (cache@v5, upload-artifact@v6)
- Update dev dependencies: ruff 0.14.9, textual 6.9.0, import-linter 2.9
- Switch scripts to use rtoml for TOML parsing

### Added
- Add rtoml to dev dependencies

## [1.0.1] - 2025-12-08

### Changed
- Update dependencies to latest versions
- Update CI/CD workflows and configuration
- Convert docstrings to Google style
- Set coverage output to JSON to avoid SQL locks

## [1.0.0] - 2025-11-04
- Bootstrap `lib_registry`
