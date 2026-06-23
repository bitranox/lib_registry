"""Platform detection, winreg import, type alias, and constant tables.

This module is the single place where ``winreg`` (or ``fake_winreg``) is
imported. All other modules import ``winreg`` from here.
"""

import platform

is_platform_windows = platform.system().lower() == "windows"

if is_platform_windows:
    import winreg  # type: ignore[import-not-found]
else:
    import fake_winreg as winreg  # type: ignore[import-untyped,no-redef]

    fake_registry = winreg.fake_reg_tools.get_minimal_windows_testregistry()  # type: ignore[attr-defined]
    winreg.load_fake_registry(fake_registry)  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Custom type
# ---------------------------------------------------------------------------

RegData = None | bytes | int | str | list[str]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

main_key_hashed_by_name: dict[str, int] = {
    "hkey_classes_root": winreg.HKEY_CLASSES_ROOT,
    "hkcr": winreg.HKEY_CLASSES_ROOT,
    "hkey_current_config": winreg.HKEY_CURRENT_CONFIG,
    "hkcc": winreg.HKEY_CURRENT_CONFIG,
    "hkey_current_user": winreg.HKEY_CURRENT_USER,
    "hkcu": winreg.HKEY_CURRENT_USER,
    "hkey_dyn_data": winreg.HKEY_DYN_DATA,
    "hkdd": winreg.HKEY_DYN_DATA,
    "hkey_local_machine": winreg.HKEY_LOCAL_MACHINE,
    "hklm": winreg.HKEY_LOCAL_MACHINE,
    "hkey_performance_data": winreg.HKEY_PERFORMANCE_DATA,
    "hkpd": winreg.HKEY_PERFORMANCE_DATA,
    "hkey_users": winreg.HKEY_USERS,
    "hku": winreg.HKEY_USERS,
}

l_hive_names: frozenset[str] = frozenset(
    {
        "HKEY_LOCAL_MACHINE",
        "HKLM",
        "HKEY_CURRENT_USER",
        "HKCU",
        "HKEY_CLASSES_ROOT",
        "HKCR",
        "HKEY_CURRENT_CONFIG",
        "HKCC",
        "HKEY_DYN_DATA",
        "HKDD",
        "HKEY_USERS",
        "HKU",
        "HKEY_PERFORMANCE_DATA",
        "HKPD",
    }
)

hive_names_hashed_by_int: dict[int, str] = {
    winreg.HKEY_CLASSES_ROOT: "HKEY_CLASSES_ROOT",
    winreg.HKEY_CURRENT_CONFIG: "HKEY_CURRENT_CONFIG",
    winreg.HKEY_CURRENT_USER: "HKEY_CURRENT_USER",
    winreg.HKEY_DYN_DATA: "HKEY_DYN_DATA",
    winreg.HKEY_LOCAL_MACHINE: "HKEY_LOCAL_MACHINE",
    winreg.HKEY_PERFORMANCE_DATA: "HKEY_PERFORMANCE_DATA",
    winreg.HKEY_USERS: "HKEY_USERS",
}

reg_type_names_hashed_by_int: dict[int, str] = {
    winreg.REG_BINARY: "REG_BINARY",
    winreg.REG_DWORD: "REG_DWORD",
    winreg.REG_DWORD_BIG_ENDIAN: "REG_DWORD_BIG_ENDIAN",
    winreg.REG_EXPAND_SZ: "REG_EXPAND_SZ",
    winreg.REG_LINK: "REG_LINK",
    winreg.REG_MULTI_SZ: "REG_MULTI_SZ",
    winreg.REG_NONE: "REG_NONE",
    winreg.REG_QWORD: "REG_QWORD",
    winreg.REG_RESOURCE_LIST: "REG_RESOURCE_LIST",
    winreg.REG_FULL_RESOURCE_DESCRIPTOR: "REG_FULL_RESOURCE_DESCRIPTOR",
    winreg.REG_RESOURCE_REQUIREMENTS_LIST: "REG_RESOURCE_REQUIREMENTS_LIST",
    winreg.REG_SZ: "REG_SZ",
}

# ---------------------------------------------------------------------------
# Windows error codes used in exception mapping
# ---------------------------------------------------------------------------

_WINERROR_FILE_NOT_FOUND = 2
_WINERROR_ACCESS_DENIED = 5
_WINERROR_INVALID_HANDLE = 6
_WINERROR_NETWORK_PATH_NOT_FOUND = 53
_WINERROR_NO_MORE_DATA = 259
_WINERROR_KEY_MARKED_FOR_DELETION = 1018
_WINERROR_NETWORK_ADDRESS_INVALID = 1707

# Re-export winreg access constants at module level for convenience
KEY_ALL_ACCESS: int = winreg.KEY_ALL_ACCESS
KEY_CREATE_LINK: int = winreg.KEY_CREATE_LINK  # type: ignore[attr-defined]
KEY_CREATE_SUB_KEY: int = winreg.KEY_CREATE_SUB_KEY  # type: ignore[attr-defined]
KEY_ENUMERATE_SUB_KEYS: int = winreg.KEY_ENUMERATE_SUB_KEYS  # type: ignore[attr-defined]
KEY_EXECUTE: int = winreg.KEY_EXECUTE  # type: ignore[attr-defined]
KEY_NOTIFY: int = winreg.KEY_NOTIFY  # type: ignore[attr-defined]
KEY_QUERY_VALUE: int = winreg.KEY_QUERY_VALUE  # type: ignore[attr-defined]
KEY_READ: int = winreg.KEY_READ
KEY_SET_VALUE: int = winreg.KEY_SET_VALUE  # type: ignore[attr-defined]
KEY_WRITE: int = winreg.KEY_WRITE  # type: ignore[attr-defined]
KEY_WOW64_32KEY: int = winreg.KEY_WOW64_32KEY  # type: ignore[attr-defined]
KEY_WOW64_64KEY: int = winreg.KEY_WOW64_64KEY  # type: ignore[attr-defined]
