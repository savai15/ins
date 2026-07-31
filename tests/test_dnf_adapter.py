"""DNF adapter tests."""

from __future__ import annotations

import output_samples as samples
from conftest import patch_runner, patch_which

from ins.adapters.dnf_adapter import DnfAdapter


def test_is_available(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.dnf_adapter", ["dnf", "rpm"])
    assert DnfAdapter().is_available() is True
    patch_which(monkeypatch, "ins.adapters.dnf_adapter", ["dnf"])
    assert DnfAdapter().is_available() is False
    patch_which(monkeypatch, "ins.adapters.dnf_adapter", ["rpm"])
    assert DnfAdapter().is_available() is False


def test_search_parses_sections(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.dnf_adapter", ["dnf", "rpm"])
    calls = patch_runner(
        monkeypatch,
        "ins.adapters.dnf_adapter",
        [(["dnf", "search"], 0, samples.DNF_SEARCH, "")],
    )

    results = DnfAdapter().search("vlc")

    names = {r.name: r for r in results}
    assert names["vlc"].description == "The portable version of VLC media player"
    assert names["vlc-core"].description == "The core components of VLC media player"
    assert names["libvlc5"].description == "library for the VLC media player"
    assert calls[0][:3] == ["dnf", "search", "-q"]


def test_search_no_matches_returns_empty(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.dnf_adapter", ["dnf", "rpm"])
    patch_runner(
        monkeypatch,
        "ins.adapters.dnf_adapter",
        [(["dnf", "search"], 1, samples.DNF_SEARCH_NO_MATCH, "")],
    )

    assert DnfAdapter().search("zzznotfound") == []


def test_list_installed_parses_rpm(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.dnf_adapter", ["dnf", "rpm"])
    calls = patch_runner(
        monkeypatch,
        "ins.adapters.dnf_adapter",
        [(["rpm", "-qa"], 0, samples.RPM_QA, "")],
    )

    installed = DnfAdapter().list_installed()

    assert calls[0][0] == "rpm"
    assert calls[0][1] == "-qa"
    assert {i.id: i.version for i in installed}["vlc"] == "3.0.20-1.fc40.x86_64"
    assert all(i.installed for i in installed)


def test_install_uses_privileged_dnf(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.dnf_adapter", ["dnf", "rpm"])
    calls = patch_runner(
        monkeypatch,
        "ins.adapters.dnf_adapter",
        [(["dnf", "install"], 0, "", "")],
    )
    monkeypatch.setattr(
        "ins.adapters._subprocess.shutil.which",
        lambda name: "/usr/bin/sudo" if name == "sudo" else None,
    )

    assert DnfAdapter().install("vlc") is True

    assert calls == [["sudo", "dnf", "install", "-y", "vlc"]]


def test_remove_uses_privileged_dnf(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.dnf_adapter", ["dnf", "rpm"])
    calls = patch_runner(
        monkeypatch,
        "ins.adapters.dnf_adapter",
        [(["dnf", "remove"], 0, "", "")],
    )
    monkeypatch.setattr(
        "ins.adapters._subprocess.shutil.which",
        lambda name: "/usr/bin/sudo" if name == "sudo" else None,
    )

    assert DnfAdapter().remove("vlc") is True

    assert calls == [["sudo", "dnf", "remove", "-y", "vlc"]]
