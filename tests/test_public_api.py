"""The names code written against lib_registry 3.0 imports keep importing.

Before 3.1.1 everything lived in ``lib_registry.registry``. The split moved the helpers, constants
and exceptions into their own modules, and ``registry.py`` re-imports them so that import path keeps
working. Those imports look unused to a linter or type checker; this test is what stops a cleanup
from deleting them.
"""

import importlib

import pytest

import lib_registry
import lib_registry.registry

#: Every public name ``src/lib_registry/registry.py`` defined in v3.1.0, the last release before the split.
NAMES_IN_REGISTRY_BEFORE_THE_SPLIT = (
    "KEY_ALL_ACCESS",
    "KEY_CREATE_LINK",
    "KEY_CREATE_SUB_KEY",
    "KEY_ENUMERATE_SUB_KEYS",
    "KEY_EXECUTE",
    "KEY_NOTIFY",
    "KEY_QUERY_VALUE",
    "KEY_READ",
    "KEY_SET_VALUE",
    "KEY_WOW64_32KEY",
    "KEY_WOW64_64KEY",
    "KEY_WRITE",
    "RegData",
    "Registry",
    "RegistryConnectionError",
    "RegistryError",
    "RegistryHKeyError",
    "RegistryHandleInvalidError",
    "RegistryKeyCreateError",
    "RegistryKeyDeleteError",
    "RegistryKeyError",
    "RegistryKeyExistsError",
    "RegistryKeyNotFoundError",
    "RegistryNetworkConnectionError",
    "RegistryValueDeleteError",
    "RegistryValueError",
    "RegistryValueNotFoundError",
    "RegistryValueWriteError",
    "get_first_part_of_the_key",
    "get_hkey_int",
    "get_key_as_string",
    "get_value_type_as_string",
    "hive_names_hashed_by_int",
    "is_platform_windows",
    "l_hive_names",
    "main_key_hashed_by_name",
    "normalize_separators",
    "reg_type_names_hashed_by_int",
    "remove_hive_from_key_str_if_present",
    "resolve_key",
    "strip_backslashes",
    "winreg",
)


@pytest.mark.os_agnostic
def test_registry_module_declares_exactly_the_names_it_held_before_the_split() -> None:
    assert sorted(lib_registry.registry.__all__) == sorted(NAMES_IN_REGISTRY_BEFORE_THE_SPLIT)


@pytest.mark.os_agnostic
@pytest.mark.parametrize("name", NAMES_IN_REGISTRY_BEFORE_THE_SPLIT)
def test_a_name_from_before_the_split_is_the_same_object_as_the_package_export(name: str) -> None:
    module = importlib.import_module("lib_registry.registry")

    assert getattr(module, name) is getattr(lib_registry, name)
