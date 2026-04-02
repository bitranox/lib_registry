"""Key parsing and formatting utilities for registry paths."""

from ._winreg_setup import (
    hive_names_hashed_by_int,
    l_hive_names,
    main_key_hashed_by_name,
    reg_type_names_hashed_by_int,
    winreg,  # noqa: F401 — used in doctests
)
from .exceptions import RegistryHKeyError


def normalize_separators(key_path: str) -> str:
    r"""Replace forward slashes with backslashes for Windows registry paths.

    Allows users to specify registry paths with ``/`` (common on Linux/macOS)
    in addition to the native ``\\`` separator.

    Args:
        key_path: Registry key path possibly containing forward slashes.

    Returns:
        The path with all ``/`` replaced by ``\\``.

    Examples:
        >>> normalize_separators('HKLM/SOFTWARE/Microsoft')
        'HKLM\\SOFTWARE\\Microsoft'
        >>> normalize_separators('HKLM\\SOFTWARE\\Microsoft')
        'HKLM\\SOFTWARE\\Microsoft'
        >>> normalize_separators('HKLM\\SOFTWARE/subkey/deep')
        'HKLM\\SOFTWARE\\subkey\\deep'
    """
    return key_path.replace("/", "\\")


def strip_backslashes(input_string: str) -> str:
    r"""Strip leading and trailing backslashes from a string.

    Args:
        input_string: The string to strip.

    Returns:
        The string with leading/trailing backslashes removed.

    Examples:
        >>> strip_backslashes('\\\\test\\\\\\\\')
        'test'
    """
    return input_string.strip("\\")


def get_first_part_of_the_key(key_name: str) -> str:
    r"""Extract the first path component from a backslash-delimited key.

    Args:
        key_name: The registry key path.

    Returns:
        The first component of the key path.

    Examples:
        >>> get_first_part_of_the_key('')
        ''
        >>> get_first_part_of_the_key('something\\\\more')
        'something'
        >>> get_first_part_of_the_key('nothing')
        'nothing'
    """
    key_name = strip_backslashes(key_name)
    return key_name.split("\\", 1)[0]


def resolve_key(key: str | int, sub_key: str = "") -> tuple[int, str]:
    r"""Parse a key specification into (hive_key, sub_key) tuple.

    Args:
        key: Either a predefined HKEY_* constant or a string containing
            the root key (e.g. ``'HKLM\\SOFTWARE'``).
        sub_key: Optional subkey path relative to *key*.

    Returns:
        Tuple of (hive_key_int, resolved_sub_key).

    Raises:
        RegistryHKeyError: If the key cannot be resolved.

    Examples:
        >>> resolve_key(winreg.HKEY_LOCAL_MACHINE)
        (..., '')
        >>> resolve_key(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\Microsoft')
        (..., 'SOFTWARE\\Microsoft')
        >>> resolve_key('HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft')
        (..., 'SOFTWARE\\Microsoft')
        >>> resolve_key('HKLM\\SOFTWARE\\Microsoft')
        (..., 'SOFTWARE\\Microsoft')
        >>> resolve_key('hklm\\SOFTWARE\\Microsoft')
        (..., 'SOFTWARE\\Microsoft')
        >>> resolve_key('HKLM/SOFTWARE/Microsoft')
        (..., 'SOFTWARE\\Microsoft')

        >>> resolve_key('HKX\\SOFTWARE\\Microsoft')
        Traceback (most recent call last):
            ...
        lib_registry.exceptions.RegistryHKeyError: invalid KEY: "HKX"

        >>> resolve_key(42, 'SOFTWARE\\Microsoft')
        Traceback (most recent call last):
            ...
        lib_registry.exceptions.RegistryHKeyError: invalid HIVE KEY: "42"
    """
    if isinstance(key, str):
        key = normalize_separators(key)
        sub_key = normalize_separators(sub_key)
        hive_key = get_hkey_int(key)
        key_without_hive = remove_hive_from_key_str_if_present(key)
        if sub_key:
            sub_key = "\\".join([key_without_hive, sub_key])
        else:
            sub_key = key_without_hive
    else:
        sub_key = normalize_separators(sub_key)
        hive_key = key
        if hive_key not in hive_names_hashed_by_int:
            raise RegistryHKeyError(f'invalid HIVE KEY: "{hive_key}"')
    return hive_key, sub_key


def get_hkey_int(key_name: str) -> int:
    r"""Extract the HKEY integer constant from a key name string.

    Accepts both short (``HKLM``) and long (``HKEY_LOCAL_MACHINE``) forms,
    case-insensitive.

    Args:
        key_name: Registry key string starting with a hive name.

    Returns:
        The integer HKEY constant.

    Raises:
        RegistryHKeyError: If the key name is not a valid hive.

    Examples:
        >>> assert get_hkey_int('HKLM\\something') == winreg.HKEY_LOCAL_MACHINE
        >>> assert get_hkey_int('hklm\\something') == winreg.HKEY_LOCAL_MACHINE
        >>> assert get_hkey_int('HKEY_LOCAL_MACHINE\\something') == winreg.HKEY_LOCAL_MACHINE
        >>> assert get_hkey_int('hkey_local_machine\\something') == winreg.HKEY_LOCAL_MACHINE
        >>> get_hkey_int('Something\\else')
        Traceback (most recent call last):
            ...
        lib_registry.exceptions.RegistryHKeyError: invalid KEY: "Something"
    """
    main_key_name = get_first_part_of_the_key(key_name)
    main_key_name_lower = main_key_name.lower()
    if main_key_name_lower in main_key_hashed_by_name:
        return int(main_key_hashed_by_name[main_key_name_lower])
    raise RegistryHKeyError(f'invalid KEY: "{main_key_name}"')


def remove_hive_from_key_str_if_present(key_name: str) -> str:
    r"""Strip the hive prefix from a key string if present.

    Args:
        key_name: Registry key string, possibly prefixed with a hive name.

    Returns:
        The key string without the hive prefix.

    Examples:
        >>> remove_hive_from_key_str_if_present('HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft')
        'SOFTWARE\\Microsoft'
        >>> remove_hive_from_key_str_if_present('hklm\\SOFTWARE\\Microsoft')
        'SOFTWARE\\Microsoft'
        >>> remove_hive_from_key_str_if_present('SOFTWARE\\Microsoft')
        'SOFTWARE\\Microsoft'
    """
    key_part_one = key_name.split("\\")[0]
    if key_part_one.upper() in l_hive_names:
        return strip_backslashes(key_name[len(key_part_one) :])
    return key_name


def get_key_as_string(key: str | int, sub_key: str = "") -> str:
    r"""Format a key specification as a human-readable string.

    Args:
        key: Either a predefined HKEY_* constant or a key string.
        sub_key: Optional subkey path relative to *key*.

    Returns:
        Formatted key string with full hive name.

    Examples:
        >>> get_key_as_string(winreg.HKEY_LOCAL_MACHINE)
        'HKEY_LOCAL_MACHINE'
        >>> get_key_as_string(winreg.HKEY_LOCAL_MACHINE, sub_key='SOFTWARE\\Microsoft')
        'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft'
        >>> get_key_as_string('hklm\\SOFTWARE\\Microsoft')
        'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft'
    """
    hive_key, sub_key = resolve_key(key, sub_key)
    return strip_backslashes(hive_names_hashed_by_int[hive_key] + "\\" + sub_key)


def get_value_type_as_string(value_type: int) -> str:
    """Return the registry value type as a human-readable string.

    Args:
        value_type: Integer registry type constant.

    Returns:
        The string name of the registry type.

    Examples:
        >>> get_value_type_as_string(winreg.REG_SZ)
        'REG_SZ'
    """
    return reg_type_names_hashed_by_int[value_type]
