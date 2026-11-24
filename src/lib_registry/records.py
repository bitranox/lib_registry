"""Named records the registry API returns in place of bare tuples.

Each record is a ``NamedTuple``, so it still unpacks, indexes and compares
like the plain tuple ``winreg`` returns: ``name, data, reg_type = value``
keeps working, and the fields can be read by name as well.

Examples:
    >>> value = RegValue("Path", "C:\\\\Windows", 1)
    >>> value.name, value.reg_type
    ('Path', 1)
    >>> name, data, reg_type = value
    >>> value == ("Path", "C:\\\\Windows", 1)
    True
    >>> KeyInfo(number_of_subkeys=2, number_of_values=3, last_modified_win_timestamp=0)
    KeyInfo(number_of_subkeys=2, number_of_values=3, last_modified_win_timestamp=0)
"""

from typing import NamedTuple

from ._winreg_setup import RegData

__all__ = ["KeyInfo", "RegValue", "ResolvedKey", "TypedValue"]


class ResolvedKey(NamedTuple):
    """A key specification split into its hive constant and the path below it.

    Attributes:
        hive_key: The predefined ``HKEY_*`` integer constant.
        sub_key: The backslash-separated path relative to the hive.
    """

    hive_key: int
    sub_key: str


class KeyInfo(NamedTuple):
    """Metadata of a registry key, as ``winreg.QueryInfoKey`` reports it.

    Attributes:
        number_of_subkeys: How many direct subkeys the key has.
        number_of_values: How many values the key holds.
        last_modified_win_timestamp: Last write time in 100 ns intervals since 1601-01-01.
    """

    number_of_subkeys: int
    number_of_values: int
    last_modified_win_timestamp: int


class TypedValue(NamedTuple):
    """A value's data together with its registry type.

    Attributes:
        data: The value data.
        reg_type: The ``REG_*`` integer type constant.
    """

    data: RegData
    reg_type: int


class RegValue(NamedTuple):
    """One named value of a registry key.

    Attributes:
        name: The value name; ``''`` for the unnamed default value.
        data: The value data.
        reg_type: The ``REG_*`` integer type constant.
    """

    name: str
    data: RegData
    reg_type: int
