# Contributing

Thanks for helping improve **lib_registry**. This page covers the day-to-day workflow and the
checks a change must pass before it merges. For the tooling details, see
[DEVELOPMENT.md](DEVELOPMENT.md).

## 1. Workflow

1. Fork and branch with a short, imperative name (`feature/cli-extension`, `fix/exit-code`).
2. Keep commits focused; leave unrelated refactors out of the change.
3. Run `make test` locally before pushing.
4. Update the docs and `CHANGELOG.md` for anything your change affects.
5. Open a pull request and reference any relevant issues.

## 2. Commits and pushes

- Write imperative commit subjects (`Add rich handler`, `Fix CLI exit codes`).
- `make test` runs the full lint/type/test pipeline and leaves the working tree untouched.
- `make push` runs the tests, commits, and pushes. Pass the message with `MSG="..."` (safe for
  any punctuation or newline). See [DEVELOPMENT.md](DEVELOPMENT.md#commit-messages).

## 3. Coding standards

- Follow Clean Architecture / SOLID: each module has one purpose and depends only on the
  layers below it.
- Keep the layer direction intact: `cli` depends on `registry`, never the reverse. CI enforces
  this with import-linter.
- Prefer small, single-purpose modules and functions.
- `snake_case` for functions and modules, `PascalCase` for classes.
- Modern type hints (`X | None` over `Optional[X]`), Google-style docstrings with doctests.
- All imports at module top; declare the public surface with `__all__`.
- Keep runtime dependencies minimal; reach for the standard library where practical.

## 4. Tests

- `make test` runs Ruff (lint + format check), Pyright (strict), import-linter, Bandit,
  pip-audit, and Pytest with coverage, including the module doctests.
- Off Windows the tests run against `fake_winreg`; on Windows they write the real registry, so
  a test that creates keys must clean them up whatever happens.
- CLI tests that create registry keys use the `temp_key` fixture in `tests/test_cli.py`: it
  makes a key unique to the test and deletes it on teardown. Tests that need a file use
  `temp_file`. Never rely on assertions passing before cleanup code runs.
- Name tests for the behavior under test and keep each case focused.
- Mark OS constraints with the markers declared in `pyproject.toml` (`@pytest.mark.os_agnostic`,
  `@pytest.mark.os_windows`, `os_posix` and the rest).
- When you add a `Registry` method or a CLI command, add its tests and update the README's API
  or CLI reference.

## 5. Before opening a PR

- [ ] `make test` passes locally.
- [ ] Docs (`README.md`, `DEVELOPMENT.md`, `docs/systemdesign/*`) are updated for the change.
- [ ] No build artifacts or virtual environments are committed.
- [ ] Version bumps touch **only** `pyproject.toml` and `CHANGELOG.md`.

## 6. Security and configuration

- Never commit secrets. Tokens (Codecov, PyPI) belong in `.env` (git-ignored) or CI secrets.
