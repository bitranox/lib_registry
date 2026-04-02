"""Metadata tales celebrating the pinned project portrait."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import runpy

import pytest
import rtoml
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
TARGET_FIELDS = ("name", "title", "version", "homepage", "author", "author_email", "shell_command")


# ---------------------------------------------------------------------------
# Pydantic models representing the pyproject.toml structure
# ---------------------------------------------------------------------------


class AuthorEntry(BaseModel):
    """Single author entry from the ``[project.authors]`` table."""

    name: str
    email: str


class ProjectUrls(BaseModel):
    """URL mapping from ``[project.urls]``."""

    Homepage: str
    Repository: str = ""
    Issues: str = ""


class ProjectTable(BaseModel):
    """The ``[project]`` table of pyproject.toml."""

    name: str
    version: str
    description: str
    classifiers: list[str] = []
    urls: ProjectUrls = ProjectUrls(Homepage="")
    authors: list[AuthorEntry] = []
    # scripts is a dynamic mapping of command names to entry points;
    # dict[str, str] is acceptable per the "small local dicts" exception.
    scripts: dict[str, str] = {}


class WheelTarget(BaseModel):
    """Wheel target configuration from ``[tool.hatch.build.targets.wheel]``."""

    packages: list[str] = []


class BuildTargets(BaseModel):
    """Build targets from ``[tool.hatch.build.targets]``."""

    wheel: WheelTarget = WheelTarget()


class HatchBuild(BaseModel):
    """Hatch build configuration from ``[tool.hatch.build]``."""

    targets: BuildTargets = BuildTargets()


class HatchConfig(BaseModel):
    """Hatch tool configuration from ``[tool.hatch]``."""

    build: HatchBuild = HatchBuild()


class ToolConfig(BaseModel):
    """The ``[tool]`` table of pyproject.toml (only hatch subset)."""

    hatch: HatchConfig = HatchConfig()


class PyprojectToml(BaseModel):
    """Top-level pyproject.toml structure (only fields used by tests)."""

    project: ProjectTable
    tool: ToolConfig = ToolConfig()


class InitConfMetadata(BaseModel):
    """Metadata constants parsed from ``__init__conf__.py``."""

    name: str
    title: str
    version: str
    homepage: str
    author: str
    author_email: str
    shell_command: str


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _load_pyproject() -> PyprojectToml:
    """Load and parse pyproject.toml into a typed Pydantic model.

    Returns:
        Validated PyprojectToml model instance.
    """
    raw = rtoml.load(PYPROJECT_PATH)
    return PyprojectToml.model_validate(raw)


def _resolve_init_conf_path(pyproject: PyprojectToml) -> Path:
    """Locate ``__init__conf__.py`` using hatch wheel package paths.

    Args:
        pyproject: Parsed pyproject.toml model.

    Returns:
        Path to the discovered ``__init__conf__.py`` file.

    Raises:
        AssertionError: If the file cannot be located.
    """
    for package_entry in pyproject.tool.hatch.build.targets.wheel.packages:
        candidate = PROJECT_ROOT / package_entry / "__init__conf__.py"
        if candidate.is_file():
            return candidate

    fallback = PROJECT_ROOT / "src" / pyproject.project.name.replace("-", "_") / "__init__conf__.py"
    if fallback.is_file():
        return fallback

    raise AssertionError("Unable to locate __init__conf__.py")


def _load_init_conf_metadata(init_conf_path: Path) -> InitConfMetadata:
    """Parse metadata constants from ``__init__conf__.py`` into a typed model.

    Extracts lines matching TARGET_FIELDS, wraps them in a TOML table,
    and validates the result into an InitConfMetadata model.

    Args:
        init_conf_path: Path to the ``__init__conf__.py`` file.

    Returns:
        Validated InitConfMetadata model instance.

    Raises:
        AssertionError: If no metadata assignments are found.
    """
    fragments: list[str] = []
    for raw_line in init_conf_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        for key in TARGET_FIELDS:
            prefix = f"{key} = "
            if stripped.startswith(prefix):
                fragments.append(stripped)
                break
    if not fragments:
        raise AssertionError("No metadata assignments found in __init__conf__.py")
    metadata_text = "[metadata]\n" + "\n".join(fragments)
    parsed = rtoml.loads(metadata_text)
    # rtoml.loads returns a dict; we extract the "metadata" sub-dict and
    # validate it into our typed model at the boundary.
    raw_metadata = parsed["metadata"]
    return InitConfMetadata.model_validate(raw_metadata)


def _load_init_conf_module(init_conf_path: Path) -> dict[str, Any]:
    """Execute ``__init__conf__.py`` and return its module namespace.

    Note: runpy.run_path() returns an inherently untyped dict[str, Any]
    representing the module namespace. This is acceptable because the
    module namespace is an arbitrary mapping of names to runtime objects,
    and cannot be meaningfully typed with a Pydantic model or dataclass.

    Args:
        init_conf_path: Path to the module file.

    Returns:
        Module namespace dictionary from runpy.run_path().
    """
    return runpy.run_path(str(init_conf_path))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.os_agnostic
def test_when_print_info_runs_it_lists_every_field(capsys: pytest.CaptureFixture[str]) -> None:
    pyproject = _load_pyproject()
    init_conf_path = _resolve_init_conf_path(pyproject)
    # runpy module namespace is inherently untyped (see _load_init_conf_module docstring)
    init_conf_module = _load_init_conf_module(init_conf_path)

    print_info = init_conf_module["print_info"]
    assert callable(print_info)

    print_info()

    captured = capsys.readouterr().out

    for label in TARGET_FIELDS:
        assert f"{label}" in captured


@pytest.mark.os_agnostic
def test_the_metadata_constants_match_the_project() -> None:
    pyproject = _load_pyproject()
    init_conf_path = _resolve_init_conf_path(pyproject)
    metadata = _load_init_conf_metadata(init_conf_path)

    assert pyproject.project.authors, "pyproject.toml must declare at least one author entry"
    assert pyproject.project.urls.Homepage, "pyproject.toml must define project.urls.Homepage"

    assert metadata.name == pyproject.project.name
    assert metadata.title == pyproject.project.description
    assert metadata.version == pyproject.project.version
    assert metadata.homepage == pyproject.project.urls.Homepage
    assert metadata.author == pyproject.project.authors[0].name
    assert metadata.author_email == pyproject.project.authors[0].email
    assert metadata.shell_command in pyproject.project.scripts
