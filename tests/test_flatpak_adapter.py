"""Flatpak adapter tests with real captured output."""

from __future__ import annotations

import output_samples as samples
from conftest import flatpak_routes, patch_runner, patch_which

from ins.adapters.flatpak_adapter import FlatpakAdapter, _human_name


def test_is_available(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.flatpak_adapter", ["flatpak"])
    assert FlatpakAdapter().is_available() is True
    patch_which(monkeypatch, "ins.adapters.flatpak_adapter", [])
    assert FlatpakAdapter().is_available() is False


def test_search_parses_columns(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.flatpak_adapter", ["flatpak"])
    calls = patch_runner(monkeypatch, "ins.adapters.flatpak_adapter", flatpak_routes())

    results = FlatpakAdapter().search("vlc")

    names = {r.id: r for r in results}
    assert names["org.videolan.VLC"].name == "VLC"
    assert names["org.videolan.VLC"].version == "3.0.20"
    assert names["org.videolan.VLC"].description.startswith("VLC media player")
    assert names["org.mozilla.firefox"].installed is True
    assert names["org.videolan.VLC"].installed is False
    assert calls[0][:3] == ["flatpak", "search", "--columns=application,version,branch,remotes,description"]


def test_search_no_matches_returns_empty(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.flatpak_adapter", ["flatpak"])
    stdout, stderr, rc = samples.FLATPAK_SEARCH_NO_MATCH
    routes = [
        (["flatpak", "search"], rc, stdout, stderr),
        (["flatpak", "list", "--user"], 0, "", ""),
        (["flatpak", "list", "--system"], 0, "", ""),
    ]
    patch_runner(monkeypatch, "ins.adapters.flatpak_adapter", routes)

    assert FlatpakAdapter().search("zzznotfound") == []


def test_list_installed_merges_user_and_system(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.flatpak_adapter", ["flatpak"])
    calls = patch_runner(monkeypatch, "ins.adapters.flatpak_adapter", flatpak_routes())

    installed = FlatpakAdapter().list_installed()

    by_id = {i.id: i for i in installed}
    assert "org.mozilla.firefox" in by_id
    assert by_id["org.mozilla.firefox"].version == "130.0"
    assert len(installed) == 1
    assert all(i.installed for i in installed)
    assert [c[2] for c in calls] == ["--user", "--system"]


def test_install_includes_remote_from_search(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.flatpak_adapter", ["flatpak"])
    calls = patch_runner(monkeypatch, "ins.adapters.flatpak_adapter", flatpak_routes())

    assert FlatpakAdapter().install("org.videolan.VLC") is True

    assert calls[-1] == ["flatpak", "install", "--user", "--noninteractive", "-y", "flathub", "org.videolan.VLC"]


def test_install_falls_back_without_remote(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.flatpak_adapter", ["flatpak"])
    routes = [
        (["flatpak", "search"], 0, "", ""),
        (["flatpak", "install"], 0, "", ""),
        (["flatpak", "uninstall"], 0, "", ""),
    ]
    calls = patch_runner(monkeypatch, "ins.adapters.flatpak_adapter", routes)

    assert FlatpakAdapter().install("org.unknown.App") is True

    assert calls[-1] == ["flatpak", "install", "--user", "--noninteractive", "-y", "org.unknown.App"]


def test_remove(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.flatpak_adapter", ["flatpak"])
    calls = patch_runner(monkeypatch, "ins.adapters.flatpak_adapter", flatpak_routes())

    assert FlatpakAdapter().remove("org.videolan.VLC") is True

    assert calls == [["flatpak", "uninstall", "--user", "-y", "org.videolan.VLC"]]


def test_human_name():
    assert _human_name("org.videolan.VLC") == "VLC"
    assert _human_name("org.mozilla.firefox") == "firefox"
