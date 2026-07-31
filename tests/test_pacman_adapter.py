"""Pacman adapter tests."""

from __future__ import annotations

from ins.adapters.pacman_adapter import PacmanAdapter

import output_samples as samples
from conftest import patch_runner, patch_which


def _routes():
    return [
        (["pacman", "-Ss"], 0, samples.PACMAN_SS, ""),
        (["pacman", "-Q"], 0, samples.PACMAN_Q, ""),
        (["pacman", "-Qu"], 0, samples.PACMAN_QU, ""),
        (["pacman", "-S"], 0, "", ""),
        (["pacman", "-R"], 0, "", ""),
    ]


def test_is_available(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.pacman_adapter", ["pacman"])
    assert PacmanAdapter().is_available() is True
    patch_which(monkeypatch, "ins.adapters.pacman_adapter", [])
    assert PacmanAdapter().is_available() is False


def test_search_parses_repo_blocks(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.pacman_adapter", ["pacman"])
    calls = patch_runner(monkeypatch, "ins.adapters.pacman_adapter", _routes())

    results = PacmanAdapter().search("vlc")

    by_name = {r.name: r for r in results}
    assert calls[0][:2] == ["pacman", "-Ss"]
    assert by_name["vlc"].version == "3.0.20-2"
    assert by_name["vlc"].description == "A multi-platform free and open-source media player"
    assert by_name["vlc"].installed is True
    assert by_name["firefox"].installed is False
    assert by_name["neovim"].description == "Fork of Vim aiming to improve user experience, plugins, and GUIs"


def test_search_no_matches_returns_empty(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.pacman_adapter", ["pacman"])
    patch_runner(monkeypatch, "ins.adapters.pacman_adapter", [(["pacman", "-Ss"], 1, "", "")])

    assert PacmanAdapter().search("zzznotfound") == []


def test_list_installed(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.pacman_adapter", ["pacman"])
    patch_runner(monkeypatch, "ins.adapters.pacman_adapter", _routes())

    installed = PacmanAdapter().list_installed()

    assert {i.id: i.version for i in installed}["vlc"] == "3.0.20-2"
    assert all(i.installed for i in installed)


def test_install_uses_privileged_pacman(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.pacman_adapter", ["pacman"])
    calls = patch_runner(monkeypatch, "ins.adapters.pacman_adapter", _routes())
    monkeypatch.setattr(
        "ins.adapters._subprocess.shutil.which",
        lambda name: "/usr/bin/sudo" if name == "sudo" else None,
    )

    assert PacmanAdapter().install("vlc") is True

    assert calls == [["sudo", "pacman", "-S", "--noconfirm", "vlc"]]


def test_remove_uses_privileged_pacman(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.pacman_adapter", ["pacman"])
    calls = patch_runner(monkeypatch, "ins.adapters.pacman_adapter", _routes())
    monkeypatch.setattr(
        "ins.adapters._subprocess.shutil.which",
        lambda name: "/usr/bin/sudo" if name == "sudo" else None,
    )

    assert PacmanAdapter().remove("vlc") is True

    assert calls == [["sudo", "pacman", "-R", "--noconfirm", "vlc"]]


def test_outdated_parses_qu(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.pacman_adapter", ["pacman"])
    calls = patch_runner(monkeypatch, "ins.adapters.pacman_adapter", _routes())

    outdated = PacmanAdapter().outdated()

    assert calls[0] == ["pacman", "-Qu"]
    by_id = {i.id: i for i in outdated}
    assert set(by_id) == {"vlc", "firefox", "zlib"}
    assert by_id["vlc"].version == "3.0.20-2"
    assert by_id["vlc"].available == "3.0.21-1"
    assert by_id["firefox"].available == "131.0-1"
    assert by_id["zlib"].version == ""
    assert by_id["zlib"].available == "1:1.3.1-1"
    assert all(i.installed for i in outdated)


def test_upgrade_uses_privileged_pacman(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.pacman_adapter", ["pacman"])
    calls = patch_runner(monkeypatch, "ins.adapters.pacman_adapter", _routes())
    monkeypatch.setattr(
        "ins.adapters._subprocess.shutil.which",
        lambda name: "/usr/bin/sudo" if name == "sudo" else None,
    )

    assert PacmanAdapter().upgrade("vlc") is True

    assert calls == [["sudo", "pacman", "-S", "--noconfirm", "vlc"]]
