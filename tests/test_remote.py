"""A Registry bound to a remote computer sends every operation through that computer's connection.

fake_winreg cannot reach another machine: its ConnectRegistry raises for every computer name. These
tests replace ``ConnectRegistry`` - the one call that leaves the machine - with a recorder that
answers with the local hive, and record which handle the key-level calls receive. Everything below
that edge is the real code and the real fake registry.
"""

import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

import pytest
from click.testing import CliRunner

import lib_registry.registry as registry_module
from lib_registry import Registry, RegistryError
from lib_registry import cli as cli_mod

_REMOTE = "remotehost"
_CURRENT_VERSION = "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion"


@dataclass
class _Wire:
    """What crossed the edge: the computer names asked for and the handles the key calls got."""

    computer_names: list[str | None] = field(default_factory=list[str | None])
    connections: list[object] = field(default_factory=list[object])
    key_call_bases: list[object] = field(default_factory=list[object])


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch) -> _Wire:
    """Record ConnectRegistry and the first argument of CreateKey/DeleteKey/DeleteKeyEx."""
    recorded = _Wire()
    winreg = registry_module.winreg
    real_connect = winreg.ConnectRegistry

    def connect(computer_name: str | None, hive: int) -> object:
        recorded.computer_names.append(computer_name)
        handle = real_connect(None, hive)
        recorded.connections.append(handle)
        return handle

    def recording(real: Callable[..., object]) -> Callable[..., object]:
        def call(base: object, *args: object) -> object:
            recorded.key_call_bases.append(base)
            return real(base, *args)

        return call

    monkeypatch.setattr(winreg, "ConnectRegistry", connect)
    for name in ("CreateKey", "DeleteKey", "DeleteKeyEx"):
        monkeypatch.setattr(winreg, name, recording(getattr(winreg, name)))
    return recorded


@pytest.fixture
def remote_key() -> Iterator[str]:
    """Name a key private to this test under HKCU and remove whatever the test left there."""
    key = f"HKCU\\Software\\lib_registry_remote_test_{uuid.uuid4().hex}"
    yield key
    with Registry() as local:
        local.delete_key(key, delete_subkeys=True, missing_ok=True)


@pytest.mark.os_agnostic
def test_a_registry_given_only_a_computer_name_reads_from_that_computer(wire: _Wire) -> None:
    with Registry(computer_name=_REMOTE) as registry:
        registry.get_value(_CURRENT_VERSION, "CurrentBuild")

    assert wire.computer_names == [_REMOTE]


@pytest.mark.os_agnostic
def test_a_registry_given_a_hive_and_a_computer_name_reads_from_that_computer(wire: _Wire) -> None:
    with Registry("HKLM", computer_name=_REMOTE) as registry:
        registry.get_value(_CURRENT_VERSION, "CurrentBuild")
        list(registry.subkeys("HKEY_USERS"))

    assert wire.computer_names == [_REMOTE, _REMOTE]


@pytest.mark.os_agnostic
def test_creating_and_deleting_keys_on_a_remote_registry_uses_its_connection(wire: _Wire, remote_key: str) -> None:
    with Registry(computer_name=_REMOTE) as registry:
        registry.create_key(f"{remote_key}\\child", parents=True)
        registry.set_value(f"{remote_key}\\child", "v", "x")
        registry.delete_key(remote_key, delete_subkeys=True)

    assert set(wire.computer_names) == {_REMOTE}
    assert wire.key_call_bases
    assert all(any(base is connection for connection in wire.connections) for base in wire.key_call_bases)


@pytest.mark.os_agnostic
def test_the_first_remote_connection_binds_the_scope_to_that_computer(wire: _Wire) -> None:
    with Registry() as registry:
        registry._reg_connect("HKLM", computer_name=_REMOTE)  # pyright: ignore[reportPrivateUsage] - the binding happens here
        list(registry.subkeys("HKEY_USERS"))

    assert wire.computer_names == [_REMOTE, _REMOTE]


@pytest.mark.os_agnostic
def test_a_registry_refuses_a_second_computer_in_the_same_scope(wire: _Wire) -> None:
    with Registry(computer_name=_REMOTE) as registry:
        registry.get_value(_CURRENT_VERSION, "CurrentBuild")

        with pytest.raises(RegistryError, match="different Machines"):
            registry._reg_connect("HKCU", computer_name="otherhost")  # pyright: ignore[reportPrivateUsage] - the guard lives here


@pytest.mark.os_agnostic
def test_the_cli_computer_option_reads_from_that_computer(wire: _Wire) -> None:
    result = CliRunner().invoke(cli_mod.cli, ["--computer", _REMOTE, "get", _CURRENT_VERSION, "CurrentBuild"])

    assert result.exit_code == 0, result.output
    assert wire.computer_names == [_REMOTE]
