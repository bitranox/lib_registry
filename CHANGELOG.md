# Changelog

All notable changes to this project will be documented in this file following
the [Keep a Changelog](https://keepachangelog.com/) format.

## [Unreleased]

## [3.0.0] 2026-04-02 18:00:15

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
