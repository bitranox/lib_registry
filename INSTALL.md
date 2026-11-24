# Installation

`lib_registry` is a normal PEP 621 package. Every method below puts the `lib_registry`
command on your PATH; `python -m lib_registry` runs the same CLI.

The examples use [uv](https://docs.astral.sh/uv/), a fast Rust-based replacement for
`pip`, `venv`, `pipx` and `poetry`. Nothing here requires uv; the plain `pip` equivalents
follow.

## Requirements

- Python 3.10 or newer, on Windows, Linux or macOS.
- Runtime dependencies, installed automatically: `rich-click` for the CLI, `rtoml`, and on
  every platform except Windows `fake_winreg`, the in-memory registry `lib_registry` works
  against there. On Windows it uses the real `winreg`.

## Install uv (optional)

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
# or, with an existing Python
python -m pip install uv
```

## 1. Into a virtual environment (uv)

```bash
uv venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
uv pip install lib_registry
uv pip install --upgrade lib_registry
# from GitHub instead of PyPI:
uv pip install "git+https://github.com/bitranox/lib_registry"
```

## 2. As a persistent CLI tool (uv)

Installs into an isolated environment and puts the command on your PATH:

```bash
uv tool install lib_registry
uv tool upgrade lib_registry
# from GitHub:
uv tool install --from "git+https://github.com/bitranox/lib_registry.git" lib_registry
```

## 3. Run once, without installing (uvx)

```bash
uvx lib_registry info
uvx --from "git+https://github.com/bitranox/lib_registry.git" lib_registry info
```

## 4. Plain pip

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install lib_registry
# from GitHub:
pip install "git+https://github.com/bitranox/lib_registry"
# editable, with dev tooling, for working on the package itself:
pip install -e ".[dev]"
```

## 5. Per-user install (no virtualenv)

```bash
pip install --user lib_registry
```

This respects PEP 668, so it is refused on an externally-managed system Python. Make sure
`~/.local/bin` (POSIX) is on your PATH so the command is found.

## 6. pipx

```bash
pipx install lib_registry
pipx upgrade lib_registry
```

## 7. From build artifacts

```bash
python -m build
pip install dist/lib_registry-*.whl
```

## Supply-chain protection

A plain `pip install`, `pipx install` or `uv tool install` takes the newest release of every
dependency at the moment you run it. To install with a cooldown, or to run the exact
dependency tree CI tests, see
[Why we recommend uv: supply-chain protection](README.md#why-we-recommend-uv-supply-chain-protection)
in the README.
