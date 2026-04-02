"""Windows registry access with a Pythonic interface.

Provide a high-level :class:`Registry` wrapper around the low-level ``winreg``
module (or ``fake_winreg`` on non-Windows platforms). Supports key creation,
deletion, value read/write, subkey iteration, SID enumeration, and remote
computer connections.

Contents:
    Registry: Context-managed registry accessor with connection caching.
    Exception hierarchy: Typed exceptions for registry operations.
    resolve_key / get_hkey_int / get_key_as_string: Key parsing utilities.
    RegData: Union type for registry value data.

Note:
    On non-Windows platforms ``fake_winreg`` provides a minimal simulated
    registry so that tests and documentation can run anywhere.

See Also:
    https://github.com/adamkerz/winreglib/blob/master/winreglib.py
"""

import pathlib
import platform
from types import TracebackType
from collections.abc import Iterator

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
# Exceptions
# ---------------------------------------------------------------------------


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


class RegistryError(Exception):
    """Base exception for all registry operations."""


class RegistryConnectionError(RegistryError):
    """Raised when a registry connection cannot be established."""


class RegistryKeyError(RegistryError):
    """Base exception for registry key operations."""


class RegistryValueError(RegistryError):
    """Base exception for registry value operations."""


class RegistryHKeyError(RegistryError):
    """Raised when an invalid HKEY constant or name is used."""


class RegistryKeyNotFoundError(RegistryKeyError):
    """Raised when a registry key does not exist."""


class RegistryKeyExistsError(RegistryKeyError):
    """Raised when a registry key already exists and exist_ok is False."""


class RegistryKeyCreateError(RegistryKeyError):
    """Raised when a registry key cannot be created."""


class RegistryKeyDeleteError(RegistryKeyError):
    """Raised when a registry key cannot be deleted."""


class RegistryValueNotFoundError(RegistryValueError):
    """Raised when a registry value does not exist."""


class RegistryValueDeleteError(RegistryValueError):
    """Raised when a registry value cannot be deleted."""


class RegistryValueWriteError(RegistryValueError):
    """Raised when a registry value cannot be written."""


class RegistryHandleInvalidError(RegistryError):
    """Raised when a registry handle is invalid."""


class RegistryNetworkConnectionError(RegistryError):
    """Raised when a remote computer cannot be reached."""


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Module-level key utilities
# ---------------------------------------------------------------------------


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
        lib_registry.registry.RegistryHKeyError: invalid KEY: "HKX"

        >>> resolve_key(42, 'SOFTWARE\\Microsoft')
        Traceback (most recent call last):
            ...
        lib_registry.registry.RegistryHKeyError: invalid HIVE KEY: "42"
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
        lib_registry.registry.RegistryHKeyError: invalid KEY: "Something"
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


# ---------------------------------------------------------------------------
# Registry class
# ---------------------------------------------------------------------------


class Registry:
    """Pythonic interface for Windows registry access.

    Wraps ``winreg`` (or ``fake_winreg`` on non-Windows) with connection
    caching, automatic key handle management, and a context manager.

    Args:
        key: Predefined HKEY_* constant, hive name string, or None.
            If provided, a connection to the hive is established immediately.
        computer_name: Remote computer in the form ``r"\\\\computer_name"``
            or ``"computer_name"``. None means local computer.

    Raises:
        RegistryNetworkConnectionError: If the remote computer is unreachable.
        RegistryHKeyError: If the hive key is invalid.

    Examples:
        >>> registry = Registry()

        >>> registry = Registry('HKCU')

        >>> Registry()._reg_connect('SPAM')
        Traceback (most recent call last):
            ...
        lib_registry.registry.RegistryHKeyError: invalid KEY: "SPAM"

        >>> Registry()._reg_connect(42)
        Traceback (most recent call last):
            ...
        lib_registry.registry.RegistryHKeyError: invalid HIVE KEY: "42"

        >>> Registry()._reg_connect(winreg.HKEY_LOCAL_MACHINE, computer_name='some_unknown_machine')
        Traceback (most recent call last):
            ...
        lib_registry.registry.RegistryNetworkConnectionError: ...

        >>> Registry()._reg_connect(winreg.HKEY_LOCAL_MACHINE, computer_name='localhost_ham_spam')
        Traceback (most recent call last):
            ...
        lib_registry.registry.RegistryNetworkConnectionError: ...
    """

    def __init__(self, key: str | int | None = None, computer_name: str | None = None) -> None:
        self.reg_hive_connections: dict[int, winreg.HKEYType] = {}
        self.computer_name = computer_name
        self._is_computer_name_set = False
        self.reg_key_handles: dict[tuple[int, str, int], winreg.HKEYType] = {}

        if key is not None:
            self._reg_connect(key=key, computer_name=computer_name)

    def __call__(self, key: str | int | None, computer_name: str | None = None) -> None:
        """Re-initialize the registry object with a new key/computer."""
        self.close_all()
        self.__init__(key, computer_name)  # type: ignore[misc]

    def __enter__(self) -> "Registry":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close_all()

    def close_all(self) -> None:
        """Close all cached key handles and hive connections.

        Called automatically by ``__exit__`` and ``__call__``.

        Examples:
            >>> registry = Registry('HKCU')
            >>> registry.close_all()
            >>> len(registry.reg_key_handles)
            0
            >>> len(registry.reg_hive_connections)
            0
        """
        for handle in self.reg_key_handles.values():
            try:
                handle.Close()
            except OSError:
                pass
        self.reg_key_handles.clear()
        for handle in self.reg_hive_connections.values():
            try:
                winreg.CloseKey(handle)  # type: ignore[attr-defined]
            except OSError:
                pass
        self.reg_hive_connections.clear()
        self._is_computer_name_set = False

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _reg_connect(self, key: str | int, computer_name: str | None = None) -> winreg.HKEYType:
        r"""Establish a connection to a predefined registry hive.

        Connections are cached and reused. Users typically do not call this
        directly; it is invoked automatically by key operations.

        Args:
            key: Predefined HKEY_* constant or hive name string.
            computer_name: Remote computer name or None for local.

        Returns:
            Handle to the opened hive.

        Raises:
            RegistryNetworkConnectionError: If the remote computer is unreachable.
            RegistryHKeyError: If the hive key is invalid.
            RegistryError: If connecting to different machines in the same scope.

        Examples:
            >>> registry = Registry('HKCU')
            >>> registry.reg_hive_connections[winreg.HKEY_CURRENT_USER]
            <...PyHKEY object at ...>
            >>> Registry()._reg_connect('HKCR')
            <...PyHKEY object at ...>
            >>> Registry()._reg_connect('HKCC')
            <...PyHKEY object at ...>
            >>> Registry()._reg_connect('HKCU')
            <...PyHKEY object at ...>
            >>> Registry()._reg_connect('HKDD')
            <...PyHKEY object at ...>
            >>> Registry()._reg_connect('HKLM')
            <...PyHKEY object at ...>
            >>> Registry()._reg_connect('HKPD')
            <...PyHKEY object at ...>
            >>> Registry()._reg_connect('HKU')
            <...PyHKEY object at ...>
            >>> Registry()._reg_connect('HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\ProfileList')
            <...PyHKEY object at ...>
            >>> Registry()._reg_connect(winreg.HKEY_LOCAL_MACHINE)
            <...PyHKEY object at ...>

            >>> Registry()._reg_connect('SPAM')
            Traceback (most recent call last):
                ...
            lib_registry.registry.RegistryHKeyError: invalid KEY: "SPAM"

            >>> Registry()._reg_connect(42)
            Traceback (most recent call last):
                ...
            lib_registry.registry.RegistryHKeyError: invalid HIVE KEY: "42"

            >>> Registry()._reg_connect(winreg.HKEY_LOCAL_MACHINE, computer_name='some_unknown_machine')
            Traceback (most recent call last):
                ...
            lib_registry.registry.RegistryNetworkConnectionError: ...

            >>> Registry()._reg_connect(winreg.HKEY_LOCAL_MACHINE, computer_name='localhost_ham_spam')
            Traceback (most recent call last):
                ...
            lib_registry.registry.RegistryNetworkConnectionError: ...
        """
        try:
            if self._is_computer_name_set and computer_name != self.computer_name:
                raise RegistryError("can not connect to different Machines in the same scope")

            hive_key, _hive_sub_key = resolve_key(key)

            if hive_key in self.reg_hive_connections:
                return self.reg_hive_connections[hive_key]

            hive_handle: winreg.HKEYType = winreg.ConnectRegistry(computer_name, hive_key)
            self.reg_hive_connections[hive_key] = hive_handle
            self._is_computer_name_set = True
            return hive_handle

        except FileNotFoundError as e_fnf:
            if hasattr(e_fnf, "winerror") and e_fnf.winerror == _WINERROR_NETWORK_PATH_NOT_FOUND:  # type: ignore[attr-defined]
                raise RegistryNetworkConnectionError(f'The network path to "{computer_name}" was not found') from None
            raise RegistryConnectionError("unknown error connecting to registry") from None

        except OSError as e_os:
            if hasattr(e_os, "winerror"):
                if e_os.winerror == _WINERROR_NETWORK_ADDRESS_INVALID:  # type: ignore[attr-defined]
                    raise RegistryNetworkConnectionError(f'The network address "{computer_name}" is invalid') from None
                if e_os.winerror == _WINERROR_INVALID_HANDLE:  # type: ignore[attr-defined]
                    raise RegistryHKeyError(f'invalid KEY: "{key}"') from None
            raise RegistryConnectionError("unknown error connecting to registry") from None

    # ------------------------------------------------------------------
    # Key handle management
    # ------------------------------------------------------------------

    def _open_key(self, key: str | int, sub_key: str = "", access: int = winreg.KEY_READ) -> winreg.HKEYType:
        r"""Open a registry key and return a cached handle.

        Opened key handles are stored by (hive_key, sub_key, access) and
        reused on subsequent calls.

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.
            access: Access mask (default ``KEY_READ``).

        Returns:
            Handle to the opened key.

        Raises:
            RegistryKeyNotFoundError: If the key does not exist.

        Examples:
            >>> registry = Registry()
            >>> h1 = registry._open_key(winreg.HKEY_LOCAL_MACHINE, sub_key='SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\ProfileList')
            >>> h2 = registry._open_key('HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\ProfileList')
            >>> assert h1 == h2

            >>> registry._open_key(winreg.HKEY_LOCAL_MACHINE, sub_key='SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\non_existing')
            Traceback (most recent call last):
                ...
            lib_registry.registry.RegistryKeyNotFoundError: registry key ... not found
        """
        hive_key, hive_sub_key = resolve_key(key, sub_key)
        cache_key = (hive_key, hive_sub_key, access)

        if cache_key in self.reg_key_handles:
            return self.reg_key_handles[cache_key]

        reg_handle = self._reg_connect(hive_key)
        try:
            key_handle: winreg.HKEYType = winreg.OpenKey(reg_handle, hive_sub_key, 0, access)
            self.reg_key_handles[cache_key] = key_handle
        except FileNotFoundError:
            key_str = get_key_as_string(key, sub_key)
            raise RegistryKeyNotFoundError(f'registry key "{key_str}" not found')
        return key_handle

    # ------------------------------------------------------------------
    # Key operations
    # ------------------------------------------------------------------

    def create_key(self, key: str | int, sub_key: str = "", exist_ok: bool = True, parents: bool = False) -> winreg.HKEYType:
        r"""Create a registry key and return a handle to it.

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.
            exist_ok: If False, raise when the key already exists.
            parents: If True, create intermediate parent keys.

        Returns:
            Handle to the created (or existing) key.

        Raises:
            RegistryKeyCreateError: If the key cannot be created.

        Examples:
            >>> registry = Registry()
            >>> registry.create_key('HKCU\\Software')
            <...PyHKEY object at ...>

            >>> registry.create_key('HKCU\\Software\\lib_registry_test', exist_ok=True)
            <...PyHKEY object at ...>

            >>> registry.create_key('HKCU\\Software\\lib_registry_test', exist_ok=False)
            Traceback (most recent call last):
                ...
            lib_registry.registry.RegistryKeyCreateError: can not create key, it already exists: HKEY_CURRENT_USER...lib_registry_test

            >>> registry.create_key('HKCU\\Software\\lib_registry_test\\a\\b', parents=False)
            Traceback (most recent call last):
                ...
            lib_registry.registry.RegistryKeyCreateError: can not create key, the parent key to "HKEY_CURRENT_USER...b" does not exist

            >>> registry.create_key('HKCU\\Software\\lib_registry_test\\a\\b', parents=True)
            <...PyHKEY object at ...>

            >>> registry.delete_key('HKCU\\Software\\lib_registry_test', delete_subkeys=True)
        """
        hive_key, hive_sub_key = resolve_key(key, sub_key)
        _key_exists = self.key_exist(hive_key, hive_sub_key)

        if (not exist_ok) and _key_exists:
            key_string = get_key_as_string(hive_key, hive_sub_key)
            raise RegistryKeyCreateError(f"can not create key, it already exists: {key_string}")

        if _key_exists:
            return self._open_key(hive_key, hive_sub_key, winreg.KEY_ALL_ACCESS)

        if not parents:
            hive_sub_key_parent = "\\".join(hive_sub_key.split("\\")[:-1])
            if not self.key_exist(hive_key, hive_sub_key_parent):
                key_str = get_key_as_string(hive_key, hive_sub_key)
                raise RegistryKeyCreateError(f'can not create key, the parent key to "{key_str}" does not exist')

        new_key_handle: winreg.HKEYType = winreg.CreateKey(hive_key, hive_sub_key)
        self.reg_key_handles[(hive_key, hive_sub_key, winreg.KEY_ALL_ACCESS)] = new_key_handle
        return new_key_handle

    def delete_key(self, key: str | int, sub_key: str = "", missing_ok: bool = False, delete_subkeys: bool = False) -> None:
        r"""Delete a registry key and optionally all its subkeys.

        If the method succeeds, the entire key including all values is removed.

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.
            missing_ok: If True, do not raise when the key is absent.
            delete_subkeys: If True, recursively delete child keys.

        Raises:
            RegistryKeyDeleteError: If the key does not exist or has subkeys.

        Examples:
            >>> registry = Registry()
            >>> registry.create_key('HKCU\\Software\\lib_registry_test\\a\\b', parents=True)
            <...PyHKEY object at ...>

            >>> assert registry.key_exist('HKCU\\Software\\lib_registry_test\\a\\b') == True
            >>> registry.delete_key('HKCU\\Software\\lib_registry_test\\a\\b')
            >>> assert registry.key_exist('HKCU\\Software\\lib_registry_test\\a\\b') == False

            >>> registry.delete_key('HKCU\\Software\\lib_registry_test\\a\\b')
            Traceback (most recent call last):
                ...
            lib_registry.registry.RegistryKeyDeleteError: can not delete key none existing key ...

            >>> registry.delete_key('HKCU\\Software\\lib_registry_test')
            Traceback (most recent call last):
                ...
            lib_registry.registry.RegistryKeyDeleteError: can not delete none empty key ...

            >>> registry.delete_key('HKCU\\Software\\lib_registry_test', delete_subkeys=True)
            >>> assert registry.key_exist('HKCU\\Software\\lib_registry_test') == False

            >>> registry.delete_key('HKCU\\Software\\lib_registry_test', missing_ok=True)
        """
        hive_key, hive_sub_key = resolve_key(key, sub_key)
        _key_exists = self.key_exist(hive_key, hive_sub_key)

        if not _key_exists:
            if missing_ok:
                return
            key_str = get_key_as_string(key, sub_key)
            raise RegistryKeyDeleteError(f'can not delete key none existing key "{key_str}"')

        if self.has_subkeys(hive_key, hive_sub_key):
            if not delete_subkeys:
                key_str = get_key_as_string(key, sub_key)
                raise RegistryKeyDeleteError(f'can not delete none empty key "{key_str}"')
            for child in self.subkeys(hive_key, hive_sub_key):
                hive_subkey_child = "\\".join([hive_sub_key, child])
                self.delete_key(hive_key, hive_subkey_child, missing_ok=True, delete_subkeys=True)

        # Close cached handles before deletion
        if (hive_key, hive_sub_key, winreg.KEY_READ) in self.reg_key_handles:
            self.reg_key_handles[(hive_key, hive_sub_key, winreg.KEY_READ)].Close()
        if (hive_key, hive_sub_key, winreg.KEY_ALL_ACCESS) in self.reg_key_handles:
            self.reg_key_handles[(hive_key, hive_sub_key, winreg.KEY_ALL_ACCESS)].Close()

        try:
            winreg.DeleteKey(hive_key, hive_sub_key)
        except OSError as e:
            # WinError 1018: key marked for deletion
            if hasattr(e, "winerror") and e.winerror == _WINERROR_KEY_MARKED_FOR_DELETION:  # type: ignore[attr-defined]
                pass
            else:
                raise

        # Remove cached handles
        self.reg_key_handles.pop((hive_key, hive_sub_key, winreg.KEY_READ), None)
        self.reg_key_handles.pop((hive_key, hive_sub_key, winreg.KEY_ALL_ACCESS), None)

    def key_exist(self, key: str | int, sub_key: str = "") -> bool:
        r"""Check whether a registry key exists.

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.

        Returns:
            True if the key exists, False otherwise.

        Examples:
            >>> Registry().key_exist('HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion')
            True
            >>> Registry().key_exist('HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows NT\\DoesNotExist')
            False
        """
        try:
            self._open_key(key=key, sub_key=sub_key)
            return True
        except RegistryKeyNotFoundError:
            return False

    def key_info(self, key: str | int, sub_key: str = "") -> tuple[int, int, int]:
        r"""Return metadata about a key as a (subkeys, values, last_modified) tuple.

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.

        Returns:
            Tuple of (number_of_subkeys, number_of_values, last_modified_timestamp).

        Examples:
            >>> registry = Registry()
            >>> registry.key_info(winreg.HKEY_USERS)
            (...)
            >>> registry.key_info('HKEY_USERS')
            (...)
        """
        key_handle = self._open_key(key=key, sub_key=sub_key)
        number_of_subkeys, number_of_values, last_modified_win_timestamp = winreg.QueryInfoKey(key_handle)
        return number_of_subkeys, number_of_values, last_modified_win_timestamp

    def number_of_subkeys(self, key: str | int, sub_key: str = "") -> int:
        r"""Return the number of subkeys for a given key.

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.

        Returns:
            Integer count of subkeys.

        Examples:
            >>> registry = Registry()
            >>> assert registry.number_of_subkeys(winreg.HKEY_USERS) > 0
            >>> assert registry.number_of_subkeys('HKEY_USERS') > 0
        """
        number_of_subkeys, _values, _ts = self.key_info(key, sub_key)
        return int(number_of_subkeys)

    def number_of_values(self, key: str | int, sub_key: str = "") -> int:
        r"""Return the number of values for a given key.

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.

        Returns:
            Integer count of values.

        Examples:
            >>> registry = Registry()
            >>> discard = registry.number_of_values(winreg.HKEY_USERS)
            >>> discard2 = registry.number_of_values('HKEY_USERS')
        """
        _subkeys, number_of_values, _ts = self.key_info(key, sub_key)
        return int(number_of_values)

    def last_access_timestamp_windows(self, key: str | int, sub_key: str = "") -> int:
        r"""Return the last-modified time as a Windows 100ns timestamp.

        The timestamp is measured in 100-nanosecond intervals since
        January 1, 1601.

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.

        Returns:
            Windows timestamp as integer.

        Examples:
            >>> registry = Registry()
            >>> discard = registry.last_access_timestamp_windows(winreg.HKEY_USERS)
            >>> discard2 = registry.last_access_timestamp_windows('HKEY_USERS')
        """
        _subkeys, _values, last_modified_win_timestamp = self.key_info(key, sub_key)
        return int(last_modified_win_timestamp)

    def last_access_timestamp(self, key: str | int, sub_key: str = "") -> float:
        r"""Return the last-modified time as a Unix epoch timestamp.

        Converts from the Windows 100ns timestamp to seconds since
        January 1, 1970 (UTC).

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.

        Returns:
            Unix timestamp as float.

        Examples:
            >>> registry = Registry()
            >>> discard = registry.last_access_timestamp(winreg.HKEY_USERS)
            >>> assert registry.last_access_timestamp('HKEY_USERS') > 1594390488.8894954
        """
        windows_timestamp_100ns = self.last_access_timestamp_windows(key, sub_key)
        linux_windows_diff_100ns = int(11644473600 * 1e7)
        linux_timestamp_100ns = windows_timestamp_100ns - linux_windows_diff_100ns
        return linux_timestamp_100ns / 1e7

    def has_subkeys(self, key: str | int, sub_key: str = "") -> bool:
        r"""Check whether a key has any subkeys.

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.

        Returns:
            True if the key has at least one subkey.

        Examples:
            >>> registry = Registry()
            >>> assert registry.has_subkeys(winreg.HKEY_USERS) == True
        """
        return self.number_of_subkeys(key=key, sub_key=sub_key) > 0

    def subkeys(self, key: str | int, sub_key: str = "") -> Iterator[str]:
        r"""Iterate over the subkey names of a registry key.

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.

        Yields:
            Subkey name strings.

        Examples:
            >>> registry = Registry()
            >>> registry.subkeys(winreg.HKEY_USERS)
            <generator object Registry.subkeys at ...>
            >>> list(registry.subkeys(winreg.HKEY_USERS))
            [...S-1-5-...']
        """
        key_handle = self._open_key(key, sub_key)
        index = 0
        while True:
            try:
                subkey = winreg.EnumKey(key_handle, index)
                index += 1
                yield subkey
            except OSError as e:
                if hasattr(e, "winerror") and e.winerror == _WINERROR_NO_MORE_DATA:  # type: ignore[attr-defined]
                    break
                raise

    def values(self, key: str | int, sub_key: str = "") -> Iterator[tuple[str, RegData, int]]:
        r"""Iterate over the values of a registry key.

        Each yielded tuple contains (value_name, value_data, value_type).

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.

        Yields:
            Tuples of (name, data, type_int).

        Examples:
            >>> registry = Registry()
            >>> registry.values('HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion')
            <generator object Registry.values at ...>
            >>> list(registry.values('HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion'))
            [...]
        """
        key_handle = self._open_key(key, sub_key)
        index = 0
        while True:
            try:
                value_name, value, value_type = winreg.EnumValue(key_handle, index)
                index += 1
                yield value_name, value, value_type
            except OSError as e:
                if hasattr(e, "winerror") and e.winerror == _WINERROR_NO_MORE_DATA:  # type: ignore[attr-defined]
                    break
                raise

    # ------------------------------------------------------------------
    # Value operations
    # ------------------------------------------------------------------

    def get_value(self, key: str | int, value_name: str | None) -> RegData:
        r"""Retrieve a value's data from the registry.

        Args:
            key: Predefined HKEY_* constant or key string.
            value_name: Name of the value. None or '' reads the default value.

        Returns:
            The value data.

        Raises:
            RegistryValueNotFoundError: If the value does not exist.

        Examples:
            >>> registry = Registry()
            >>> registry.get_value('HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion', 'CurrentBuild')
            '...'

            >>> registry.get_value('HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion', 'DoesNotExist')
            Traceback (most recent call last):
                ...
            lib_registry.registry.RegistryValueNotFoundError: value "DoesNotExist" not found in key "...CurrentVersion"
        """
        result, _result_type = self.get_value_ex(key, value_name)
        return result

    def get_value_ex(self, key: str | int, value_name: str | None) -> tuple[RegData, int]:
        r"""Retrieve a value's data and type from the registry.

        Args:
            key: Predefined HKEY_* constant or key string.
            value_name: Name of the value. None or '' reads the default value.

        Returns:
            Tuple of (value_data, value_type_int).

        Raises:
            RegistryValueNotFoundError: If the value does not exist.

        Examples:
            >>> registry = Registry()
            >>> registry.get_value_ex('HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion', 'CurrentBuild')
            (...)

            >>> registry.get_value_ex('HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion', 'DoesNotExist')
            Traceback (most recent call last):
                ...
            lib_registry.registry.RegistryValueNotFoundError: value "DoesNotExist" not found in key "...CurrentVersion"
        """
        if value_name is None:
            value_name = ""

        key_handle = self._open_key(key)
        try:
            reg_value, reg_type = winreg.QueryValueEx(key_handle, value_name)
            return reg_value, reg_type
        except FileNotFoundError:
            key_str = get_key_as_string(key)
            raise RegistryValueNotFoundError(f'value "{value_name}" not found in key "{key_str}"')

    def set_value(self, key: str | int, value_name: str | None, value: RegData, value_type: int | None = None) -> None:
        r"""Write a value to the registry.

        If *value_type* is not given, it is inferred from the Python type:

        ==================  =============
        Python type         REG_TYPE
        ==================  =============
        None                REG_NONE
        str                 REG_SZ
        list[str]           REG_MULTI_SZ
        bytes               REG_BINARY
        int                 REG_DWORD
        everything else     REG_BINARY
        ==================  =============

        Args:
            key: Predefined HKEY_* constant or key string.
            value_name: Name of the value. None or '' writes the default value.
            value: The data to write.
            value_type: Optional explicit registry type constant.

        Raises:
            RegistryValueWriteError: If the value cannot be written.

        Examples:
            >>> registry = Registry()
            >>> registry.create_key('HKCU\\Software\\lib_registry_test', parents=True)
            <...PyHKEY object at ...>

            >>> registry.set_value(key='HKCU\\Software\\lib_registry_test', value_name='test_REG_SZ', value='test_string', value_type=winreg.REG_SZ)
            >>> assert registry.get_value_ex(key='HKCU\\Software\\lib_registry_test', value_name='test_REG_SZ') == ('test_string', 1)

            >>> registry.set_value(key='HKCU\\Software\\lib_registry_test', value_name='test_REG_MULTI_SZ', value=['str1', 'str2'], value_type=winreg.REG_MULTI_SZ)
            >>> assert registry.get_value_ex(key='HKCU\\Software\\lib_registry_test', value_name='test_REG_MULTI_SZ') == (['str1', 'str2'], 7)

            >>> binary_test_value=(chr(128512) * 10).encode('utf-8')
            >>> registry.set_value(key='HKCU\\Software\\lib_registry_test', value_name='test_REG_BINARY', value=binary_test_value, value_type=winreg.REG_BINARY)
            >>> assert registry.get_value_ex(key='HKCU\\Software\\lib_registry_test', value_name='test_REG_BINARY') == (binary_test_value, 3)

            >>> registry.set_value(key='HKCU\\Software\\lib_registry_test', value_name='test_REG_DWORD', value=123456, value_type=winreg.REG_DWORD)
            >>> assert registry.get_value_ex(key='HKCU\\Software\\lib_registry_test', value_name='test_REG_DWORD') == (123456, 4)

            >>> registry.set_value(key='HKCU\\Software\\lib_registry_test', value_name='test_auto_str', value='test_string')
            >>> assert registry.get_value_ex(key='HKCU\\Software\\lib_registry_test', value_name='test_auto_str') == ('test_string', 1)

            >>> registry.set_value(key='HKCU\\Software\\lib_registry_test', value_name='test_auto_int', value=123456)
            >>> assert registry.get_value_ex(key='HKCU\\Software\\lib_registry_test', value_name='test_auto_int') == (123456, 4)

            >>> registry.delete_key('HKCU\\Software\\lib_registry_test', missing_ok=True, delete_subkeys=True)
        """
        if value_name is None:
            value_name = ""

        if value_type is None:
            value_type = self._infer_value_type(value)

        key_handle = self._open_key(key, access=winreg.KEY_ALL_ACCESS)
        try:
            winreg.SetValueEx(key_handle, value_name, 0, value_type, value)  # type: ignore[arg-type]
        except (OSError, TypeError, OverflowError) as exc:
            key_str = get_key_as_string(key)
            value_type_str = get_value_type_as_string(value_type)
            raise RegistryValueWriteError(f'can not write data to key "{key_str}", value_name "{value_name}", value_type "{value_type_str}"') from exc

    @staticmethod
    def _infer_value_type(value: RegData) -> int:
        """Infer the registry type from a Python value."""
        if value is None:
            return winreg.REG_NONE
        if isinstance(value, int):
            return winreg.REG_DWORD
        if isinstance(value, list):
            return winreg.REG_MULTI_SZ
        if isinstance(value, str):
            return winreg.REG_SZ
        return winreg.REG_BINARY

    def delete_value(self, key: str | int, value_name: str | None) -> None:
        r"""Delete a value from a registry key.

        Args:
            key: Predefined HKEY_* constant or key string.
            value_name: Name of the value. None or '' deletes the default value.

        Raises:
            RegistryValueDeleteError: If the value cannot be deleted.

        Examples:
            >>> registry = Registry()
            >>> my_key_handle = registry.create_key('HKCU\\Software\\lib_registry_test', parents=True)
            >>> registry.set_value(key='HKCU\\Software\\lib_registry_test', value_name='test_name', value='test_string', value_type=winreg.REG_SZ)
            >>> assert registry.get_value_ex(key='HKCU\\Software\\lib_registry_test', value_name='test_name') == ('test_string', 1)

            >>> registry.delete_value(key='HKCU\\Software\\lib_registry_test', value_name='test_name')
            >>> registry.get_value_ex(key='HKCU\\Software\\lib_registry_test', value_name='test_name')
            Traceback (most recent call last):
                ...
            lib_registry.registry.RegistryValueNotFoundError: value "test_name" not found in key "HKEY_CURRENT_USER..."

            >>> registry.delete_key('HKCU\\Software\\lib_registry_test', missing_ok=True, delete_subkeys=True)
        """
        if value_name is None:
            value_name = ""

        key_handle = self._open_key(key, access=winreg.KEY_ALL_ACCESS)
        try:
            winreg.DeleteValue(key_handle, value_name)
        except FileNotFoundError as e:
            if hasattr(e, "winerror") and e.winerror == _WINERROR_FILE_NOT_FOUND:  # type: ignore[attr-defined]
                key_str = get_key_as_string(key)
                raise RegistryValueDeleteError(f'can not delete value "{value_name}" from key "{key_str}"') from e
            raise

    # ------------------------------------------------------------------
    # SID / user methods
    # ------------------------------------------------------------------

    def sids(self) -> Iterator[str]:
        r"""Iterate over Windows Security Identifiers from the ProfileList.

        Yields:
            SID strings.

        Examples:
            >>> registry = Registry()
            >>> list(registry.sids())
            ['S-1-5-...']
        """
        key = "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\ProfileList"
        yield from self.subkeys(key)

    def username_from_sid(self, sid: str) -> str:
        """Resolve a Windows username from a Security Identifier.

        Tries the Volatile Environment first, then falls back to the
        ProfileImagePath in the ProfileList.

        Args:
            sid: The Security Identifier string.

        Returns:
            The resolved username.

        Raises:
            RegistryError: If the username cannot be determined.

        Examples:
            >>> l_users = list()
            >>> registry = Registry()
            >>> for my_sid in registry.sids():
            ...     try:
            ...         my_username = registry.username_from_sid(my_sid)
            ...         l_users.append(my_username)
            ...     except RegistryKeyNotFoundError:
            ...         pass
            >>> l_users
            [...]
        """
        try:
            username = self._get_username_from_volatile_environment(sid)
            if username:
                return username
        except RegistryError:
            pass

        try:
            username = self._get_username_from_profile_list(sid)
        except RegistryError:
            raise RegistryError(f'can not determine User for SID "{sid}"')
        if not username:
            raise RegistryError(f'can not determine User for SID "{sid}"')
        return username

    def _get_username_from_profile_list(self, sid: str) -> str:
        r"""Get username by SID from the ProfileImagePath.

        Args:
            sid: The Security Identifier string.

        Returns:
            The username extracted from the profile path.

        Raises:
            RegistryKeyNotFoundError: If the SID key does not exist.

        Examples:
            >>> registry = Registry()
            >>> for my_sid in registry.sids():
            ...     try:
            ...         registry._get_username_from_profile_list(my_sid)
            ...         break
            ...     except RegistryKeyNotFoundError:
            ...         pass
            '...'

            >>> registry._get_username_from_profile_list('unknown')
            Traceback (most recent call last):
                ...
            lib_registry.registry.RegistryKeyNotFoundError: registry key "...unknown" not found
        """
        value, _value_type = self.get_value_ex(
            f"HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\ProfileList\\{sid}",
            "ProfileImagePath",
        )
        if not isinstance(value, str):
            raise RegistryError(f'Expected string ProfileImagePath for SID "{sid}"')
        return pathlib.PureWindowsPath(value).name

    def _get_username_from_volatile_environment(self, sid: str) -> str:
        r"""Get username by SID from the Volatile Environment.

        Args:
            sid: The Security Identifier string.

        Returns:
            The username from the volatile environment.

        Raises:
            RegistryKeyNotFoundError: If the volatile environment key does not exist.

        Examples:
            >>> registry = Registry()
            >>> import os
            >>> if 'TRAVIS' not in os.environ:
            ...     for my_sid in registry.sids():
            ...         try:
            ...             registry._get_username_from_volatile_environment(my_sid)
            ...             break
            ...         except RegistryKeyNotFoundError:
            ...             pass
            ... else:
            ...   print("'pass'")
            '...'
        """
        value, _value_type = self.get_value_ex(f"HKEY_USERS\\{sid}\\Volatile Environment", "USERNAME")
        if not isinstance(value, str):
            raise RegistryError(f'Expected string USERNAME for SID "{sid}"')
        return value

    # ------------------------------------------------------------------
    # Extended key operations
    # ------------------------------------------------------------------

    def create_key_ex(self, key: str | int, sub_key: str = "", access: int = winreg.KEY_WRITE) -> winreg.HKEYType:
        r"""Create a registry key with explicit access control.

        Unlike :meth:`create_key`, this wraps ``winreg.CreateKeyEx`` and
        allows specifying the access mask directly.

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.
            access: Access mask for the returned handle (default ``KEY_WRITE``).

        Returns:
            Handle to the created (or existing) key.

        Examples:
            >>> registry = Registry()
            >>> h = registry.create_key_ex('HKCU\\Software\\lib_registry_test_ex')
            >>> registry.delete_key('HKCU\\Software\\lib_registry_test_ex', missing_ok=True)
        """
        hive_key, hive_sub_key = resolve_key(key, sub_key)
        reg_handle = self._reg_connect(hive_key)
        key_handle: winreg.HKEYType = winreg.CreateKeyEx(reg_handle, hive_sub_key, 0, access)  # type: ignore[call-arg]
        self.reg_key_handles[(hive_key, hive_sub_key, access)] = key_handle
        return key_handle

    def delete_key_ex(self, key: str | int, sub_key: str = "", access: int = winreg.KEY_WOW64_64KEY) -> None:  # type: ignore[attr-defined]
        r"""Delete a registry key with WOW64 view control.

        Wraps ``winreg.DeleteKeyEx`` which supports specifying the registry
        view (32-bit or 64-bit) on 64-bit Windows.

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.
            access: Access mask controlling the registry view
                (default ``KEY_WOW64_64KEY``).

        Raises:
            RegistryKeyDeleteError: If the key cannot be deleted.

        Examples:
            >>> registry = Registry()
            >>> registry.create_key('HKCU\\Software\\lib_registry_test_dex', parents=True)
            <...PyHKEY object at ...>
            >>> registry.delete_key_ex('HKCU\\Software\\lib_registry_test_dex')
            >>> assert registry.key_exist('HKCU\\Software\\lib_registry_test_dex') == False
        """
        hive_key, hive_sub_key = resolve_key(key, sub_key)
        try:
            winreg.DeleteKeyEx(hive_key, hive_sub_key, access, 0)  # type: ignore[attr-defined]
        except FileNotFoundError:
            key_str = get_key_as_string(key, sub_key)
            raise RegistryKeyDeleteError(f'can not delete key "{key_str}"') from None
        # Clean ALL cached handles for this key (any access mask)
        stale_keys = [k for k in self.reg_key_handles if k[0] == hive_key and k[1] == hive_sub_key]
        for k in stale_keys:
            try:
                self.reg_key_handles[k].Close()
            except OSError:
                pass
            del self.reg_key_handles[k]

    def close_key(self, key: str | int, sub_key: str = "") -> None:
        r"""Explicitly close a registry key handle and remove it from cache.

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.

        Examples:
            >>> registry = Registry()
            >>> registry._open_key('HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion')
            <...PyHKEY object at ...>
            >>> registry.close_key('HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion')
        """
        hive_key, hive_sub_key = resolve_key(key, sub_key)
        for access in (winreg.KEY_READ, winreg.KEY_ALL_ACCESS):
            cache_key = (hive_key, hive_sub_key, access)
            handle = self.reg_key_handles.pop(cache_key, None)
            if handle is not None:
                winreg.CloseKey(handle)  # type: ignore[attr-defined]

    def flush_key(self, key: str | int, sub_key: str = "") -> None:
        r"""Write all attributes of a key to the registry on disk.

        Calling this is rarely necessary; the registry flushes automatically
        when closed. Use this only when an application requires absolute
        certainty that registry data is on disk.

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.

        Examples:
            >>> registry = Registry()
            >>> registry.create_key('HKCU\\Software\\lib_registry_test_flush', parents=True)
            <...PyHKEY object at ...>
            >>> registry.flush_key('HKCU\\Software\\lib_registry_test_flush')
            >>> registry.delete_key('HKCU\\Software\\lib_registry_test_flush', missing_ok=True)
        """
        key_handle = self._open_key(key, sub_key, access=winreg.KEY_ALL_ACCESS)
        winreg.FlushKey(key_handle)  # type: ignore[attr-defined]

    def save_key(self, key: str | int, file_name: str, sub_key: str = "") -> None:
        r"""Save a registry key and all subkeys/values to a file.

        On real Windows this produces a binary hive file. With fake_winreg
        the output is JSON.

        Args:
            key: Predefined HKEY_* constant or key string.
            file_name: Path to the output file.
            sub_key: Subkey path relative to *key*.

        Note:
            Parameter order differs from :meth:`load_key` because *sub_key*
            is optional here (defaults to the key itself) but required for
            load.

        Examples:
            >>> import tempfile, os, platform
            >>> registry = Registry()
            >>> fp = os.path.join(tempfile.gettempdir(), '_lib_reg_save_test.json')
            >>> if platform.system() != 'Windows':
            ...     registry.save_key('HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion', fp)
            ...     assert os.path.isfile(fp)
            ...     os.remove(fp)
        """
        key_handle = self._open_key(key, sub_key)
        winreg.SaveKey(key_handle, file_name)  # type: ignore[attr-defined]

    def load_key(self, key: str | int, sub_key: str, file_name: str) -> None:
        r"""Load registry data from a file into a subkey.

        On real Windows this loads a binary hive file. With fake_winreg
        the input is the JSON format produced by :meth:`save_key`.

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey under *key* where data will be loaded.
            file_name: Path to the input file.

        Examples:
            >>> import tempfile, os, platform
            >>> registry = Registry()
            >>> fp = os.path.join(tempfile.gettempdir(), '_lib_reg_load_test.json')
            >>> if platform.system() != 'Windows':
            ...     registry.save_key('HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion', fp)
            ...     registry.load_key(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\_load_test', fp)
            ...     assert registry.key_exist('HKLM\\SOFTWARE\\_load_test')
            ...     os.remove(fp)
        """
        hive_key, _hive_sub_key = resolve_key(key)
        reg_handle = self._reg_connect(hive_key)
        winreg.LoadKey(reg_handle, normalize_separators(sub_key), file_name)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Reflection control (64-bit Windows)
    # ------------------------------------------------------------------

    def disable_reflection_key(self, key: str | int, sub_key: str = "") -> None:
        r"""Disable registry reflection for a 32-bit process on 64-bit Windows.

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.

        Examples:
            >>> registry = Registry()
            >>> h = registry._open_key('HKCU\\Software')
            >>> registry.disable_reflection_key('HKCU\\Software')
        """
        key_handle = self._open_key(key, sub_key)
        winreg.DisableReflectionKey(key_handle)  # type: ignore[attr-defined]

    def enable_reflection_key(self, key: str | int, sub_key: str = "") -> None:
        r"""Re-enable registry reflection for a key previously disabled.

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.

        Examples:
            >>> registry = Registry()
            >>> h = registry._open_key('HKCU\\Software')
            >>> registry.enable_reflection_key('HKCU\\Software')
        """
        key_handle = self._open_key(key, sub_key)
        winreg.EnableReflectionKey(key_handle)  # type: ignore[attr-defined]

    def query_reflection_key(self, key: str | int, sub_key: str = "") -> bool:
        r"""Check whether registry reflection is disabled for a key.

        Args:
            key: Predefined HKEY_* constant or key string.
            sub_key: Subkey path relative to *key*.

        Returns:
            True if reflection is disabled, False otherwise.

        Examples:
            >>> registry = Registry()
            >>> h = registry._open_key('HKCU\\Software')
            >>> isinstance(registry.query_reflection_key('HKCU\\Software'), bool)
            True
        """
        key_handle = self._open_key(key, sub_key)
        return bool(winreg.QueryReflectionKey(key_handle))  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def expand_environment_strings(string: str) -> str:
        r"""Expand environment variable references in a string.

        Expands ``%ENVVAR%`` style placeholders using the Windows
        environment. On non-Windows platforms, this delegates to
        ``fake_winreg.ExpandEnvironmentStrings``.

        Args:
            string: String containing ``%ENVVAR%`` references.

        Returns:
            The string with environment variables expanded.

        Examples:
            >>> import os
            >>> os.environ['LIB_REG_TEST_VAR'] = 'hello'
            >>> Registry.expand_environment_strings('%LIB_REG_TEST_VAR%')
            'hello'
            >>> del os.environ['LIB_REG_TEST_VAR']
        """
        return winreg.ExpandEnvironmentStrings(string)  # type: ignore[attr-defined,no-any-return]


__all__ = [
    # Type
    "RegData",
    # Constants
    "main_key_hashed_by_name",
    "l_hive_names",
    "hive_names_hashed_by_int",
    "reg_type_names_hashed_by_int",
    "winreg",
    "is_platform_windows",
    # Exceptions
    "RegistryError",
    "RegistryConnectionError",
    "RegistryKeyError",
    "RegistryValueError",
    "RegistryHKeyError",
    "RegistryKeyNotFoundError",
    "RegistryKeyExistsError",
    "RegistryKeyCreateError",
    "RegistryKeyDeleteError",
    "RegistryValueNotFoundError",
    "RegistryValueDeleteError",
    "RegistryValueWriteError",
    "RegistryHandleInvalidError",
    "RegistryNetworkConnectionError",
    # Helpers
    "normalize_separators",
    "strip_backslashes",
    "get_first_part_of_the_key",
    # Key utilities
    "resolve_key",
    "get_hkey_int",
    "remove_hive_from_key_str_if_present",
    "get_key_as_string",
    "get_value_type_as_string",
    # Main class
    "Registry",
    # Re-exported winreg constants (convenience)
    "KEY_ALL_ACCESS",
    "KEY_CREATE_LINK",
    "KEY_CREATE_SUB_KEY",
    "KEY_ENUMERATE_SUB_KEYS",
    "KEY_EXECUTE",
    "KEY_NOTIFY",
    "KEY_QUERY_VALUE",
    "KEY_READ",
    "KEY_SET_VALUE",
    "KEY_WRITE",
    "KEY_WOW64_32KEY",
    "KEY_WOW64_64KEY",
]

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
