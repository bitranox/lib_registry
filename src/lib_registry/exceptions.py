"""Typed exception hierarchy for registry operations."""


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
