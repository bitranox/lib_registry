# Development

The `Makefile` is a thin wrapper around [bmk](https://pypi.org/project/bmk/), the bitranox
build/test/release runner. It does not contain project logic; it forwards each target to bmk.

Do not edit the `Makefile`. Its first line (`# BMK MAKEFILE <version>`) marks it as
generated, and bmk overwrites it on upgrade.

## How bmk is wired

- bmk is installed once per machine, in uv's own tool directory, and holds only itself and
  its toolchain (pyright, ruff, and so on).
- The project's dependencies live in the project's own `.venv`, which bmk provisions and
  syncs from `pyproject.toml` and `uv.lock`. That `.venv` is the environment the tests,
  pyright and pip-audit all run against.
- The `.venv` is disposable: delete it and the next `make` rebuilds it.

You need `uv` and `make` on PATH; bmk bootstraps itself on first use.

## Common targets

Trailing arguments are forwarded to bmk (`make test --verbose`). Run `make help` for the
complete, authoritative list; the table below is the everyday subset.

| Target                | Aliases           | What it does                                            |
|-----------------------|-------------------|---------------------------------------------------------|
| `test`                | `t`               | Full local gate: lint, type-check, tests with coverage. |
| `test-all`            |                   | Run pytest + pyright on every declared Python version.  |
| `codecov`             | `coverage`, `cov` | Upload the coverage report to Codecov.                  |
| `build`               | `bld`             | Build wheel and sdist.                                  |
| `run`                 |                   | Run the project CLI.                                    |
| `clean`               | `cln`, `cl`       | Remove build artifacts and caches.                      |
| `bump-patch`          |                   | Bump patch version `X.Y.(Z+1)`.                         |
| `bump-minor`          |                   | Bump minor version `X.(Y+1).0`.                         |
| `bump-major`          |                   | Bump major version `(X+1).0.0`.                         |
| `commit`              | `c`               | Commit with a timestamped message.                      |
| `push`                | `psh`, `p`        | Run tests, commit, and push.                            |
| `release`             | `rel`, `r`        | Create a versioned release (tag + GitHub release).      |
| `ship`                | `sh`              | Push, wait for CI, release, wait for release CI.        |
| `dependencies`        | `deps`, `d`       | Check and list project dependencies.                    |
| `dependencies-update` |                   | Update dependencies to their latest versions.           |
| `dev`                 |                   | Editable install with dev extras.                       |
| `install`             |                   | Editable install, no dev extras.                        |
| `info`                |                   | Print resolved package metadata.                        |
| `version-current`     |                   | Print the current version.                              |

## What `make test` runs

`make test` is the single local gate and mirrors CI: Ruff (lint + format check), Pyright in
strict mode, import-linter (the CLI-depends-on-domain layers contract), Bandit, pip-audit,
and Pytest with coverage, including the doctests in the source modules. Coverage must reach
70% (`[tool.coverage.report] fail_under`).

Off Windows the suite runs against `fake_winreg`, an in-memory registry loaded with a
minimal Windows test registry; on Windows it runs against the real one. Tests carry an OS
marker (`os_agnostic`, `os_windows`, `os_posix` and the rest declared in `pyproject.toml`).

## Commit messages

Pass a commit message with `MSG=`, not `ARGS=`:

```bash
make push MSG="fix(cli): correct exit code on --no-traceback"
```

`ARGS=` is re-parsed by the shell, so punctuation like `( ) ; $` breaks or executes and a
newline is impossible. `MSG=` is passed through the environment and is safe for any text.
With no message, `make push fix the thing` also works: bare trailing words become a plain
one-line message.

## Versioning and metadata

- `pyproject.toml` `[project]` is the single source of truth for version and metadata.
- `src/lib_registry/__init__conf__.py` holds static constants synced from `pyproject.toml`
  by automation (`make bump-*`, `make commit` and `make push`). Runtime code imports these
  constants instead of querying `importlib.metadata`.
- Bump only through `make bump-patch` / `-minor` / `-major`; never hand-edit the version.
- Write the changelog entry under `## [Unreleased]` in `CHANGELOG.md` before bumping: the
  bump turns that heading into the release heading.
- The console command name lives in `pyproject.toml` `[project.scripts]`.

## Releasing

1. Bump the version and make sure `CHANGELOG.md` describes the release.
2. `make release` tags the commit and creates the GitHub release, or `make ship` pushes,
   waits for CI to pass, then releases.
3. CI publishes to PyPI from the tag through an OIDC Trusted Publisher.

## Continuous integration

Workflows live under `.github/workflows/` and are managed by the shared
`default_cicd_public` template. Do not edit them in this repo.

- `default_cicd_public.yml` - lint, type-check and test on `ubuntu-latest`, `windows-latest`
  and `macos-latest` (`[tool.ci] os`) and on every Python version the `pyproject.toml`
  classifiers declare (3.10 through 3.15), then build.
- `default_release_public.yml` - on a `v*.*.*` tag, build and publish to PyPI.
- `codeql.yml` - CodeQL security analysis.
