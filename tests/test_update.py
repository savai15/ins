"""Part 8 tests: `ins -u` update-all command and per-adapter update counts."""

from __future__ import annotations

import pytest

import ins.cli as cli
from ins.adapters._subprocess import AdapterError
from ins.adapters.apk_adapter import ApkAdapter
from ins.adapters.apt_adapter import AptAdapter
from ins.adapters.dnf_adapter import DnfAdapter
from ins.adapters.flatpak_adapter import FlatpakAdapter
from ins.adapters.nix_adapter import NixAdapter
from ins.adapters.pacman_adapter import PacmanAdapter
from ins.adapters.zypper_adapter import ZypperAdapter

from conftest import patch_runner, patch_which


# ---------------------------------------------------------------- CLI level

def test_update_fake_summary(fake_env, capsys):
    rc = cli.main(["-u"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "6 packages updated across fake, fake2" in out


def test_update_source_filter(fake_env, capsys):
    rc = cli.main(["-u", "--s", "fake"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "3 packages updated across fake" in out
    assert "fake2" not in out


def test_update_unknown_source(fake_env, capsys):
    rc = cli.main(["-u", "--s", "bogus"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "unknown source 'bogus'" in err


def test_update_failure_reported(fake_env, capsys, monkeypatch):
    from ins.adapters import fake_adapter as fa

    def boom(self, on_progress=None):
        raise AdapterError("refresh failed")

    monkeypatch.setattr(fa.FakeAdapter, "update", boom)
    rc = cli.main(["-u"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "refresh failed" in err
    assert "error: 2 source(s) failed" in err


# ------------------------------------------------------------ adapter level

def test_apt_update_counts_upgradable(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apt_adapter", ["apt-get"])
    routes = [
        (["apt-get", "update"], 0,
         "Hit:1 http://deb.debian.org/debian bookworm InRelease\n"
         "Reading package lists... Done\n"
         "2 packages can be upgraded. Run 'apt list --upgradable' for them.\n", ""),
    ]
    calls = patch_runner(monkeypatch, "ins.adapters.apt_adapter", routes)

    assert AptAdapter().update() == 2
    assert calls[0][0] in ("sudo", "pkexec")
    assert calls[0][1:] == ["apt-get", "update"]


def test_apt_update_streams_and_counts(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apt_adapter", ["apt-get"])
    routes = [
        (["apt-get", "update"], 0, "1 package can be upgraded.\n", ""),
    ]
    patch_runner(monkeypatch, "ins.adapters.apt_adapter", routes)

    seen: list[str] = []
    assert AptAdapter().update(on_progress=seen.append) == 1
    assert seen == ["1 package can be upgraded."]


def test_apt_update_zero_when_quiet(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apt_adapter", ["apt-get"])
    routes = [(["apt-get", "update"], 0, "Reading package lists... Done\n", "")]
    patch_runner(monkeypatch, "ins.adapters.apt_adapter", routes)

    assert AptAdapter().update() == 0


def test_flatpak_update_user_level_counts(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.flatpak_adapter", ["flatpak"])
    routes = [
        (["flatpak", "update", "--user", "--noninteractive", "-y"], 0,
         "Looking for updates…\nUpdated org.videolan.VLC\n", ""),
    ]
    calls = patch_runner(monkeypatch, "ins.adapters.flatpak_adapter", routes)

    assert FlatpakAdapter().update() == 1
    assert calls[0][0] == "flatpak"


def test_dnf_update_counts_upgraded(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.dnf_adapter", ["dnf"])
    routes = [
        (["dnf", "upgrade", "-y"], 0,
         "Dependencies resolved.\nUpgraded:\n  firefox-131.0-1.fc40.x86_64\n  vlc-3.1.0-1.fc40.x86_64\nComplete!\n", ""),
    ]
    calls = patch_runner(monkeypatch, "ins.adapters.dnf_adapter", routes)

    assert DnfAdapter().update() == 2
    assert calls[0][0] in ("sudo", "pkexec")
    assert calls[0][1:] == ["dnf", "upgrade", "-y"]


def test_dnf_update_nothing_to_do(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.dnf_adapter", ["dnf"])
    routes = [(["dnf", "upgrade", "-y"], 0, "Dependencies resolved.\nNothing to do.\n", "")]
    patch_runner(monkeypatch, "ins.adapters.dnf_adapter", routes)

    assert DnfAdapter().update() == 0


@pytest.mark.parametrize(
    ("module", "cls", "bin", "cmd", "timeout"),
    [
        ("ins.adapters.pacman_adapter", PacmanAdapter, "pacman", ["pacman", "-Sy"], 600),
        ("ins.adapters.zypper_adapter", ZypperAdapter, "zypper", ["zypper", "-n", "refresh"], 600),
        ("ins.adapters.apk_adapter", ApkAdapter, "apk", ["apk", "update"], 600),
    ],
)
def test_update_refresh_sources_returns_zero(monkeypatch, module, cls, bin, cmd, timeout):
    patch_which(monkeypatch, module, [bin])
    routes = [(cmd, 0, "done\n", "")]
    calls = patch_runner(monkeypatch, module, routes)

    assert cls().update() == 0
    assert calls[0][0] in ("sudo", "pkexec")
    assert calls[0][1:] == cmd


def test_nix_update_user_level(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.nix_adapter", ["nix-env"])
    routes = [(["nix-channel", "--update"], 0, "unpacking channels...\n", "")]
    calls = patch_runner(monkeypatch, "ins.adapters.nix_adapter", routes)

    assert NixAdapter().update() == 0
    assert calls[0][0] == "nix-channel"
