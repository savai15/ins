"""Snap adapter tests (Part 3 completion)."""

from __future__ import annotations

import pytest
from ins.adapters.snap_adapter import SnapAdapter

import output_samples
from conftest import patch_runner, patch_which


@pytest.fixture
def snap_env(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.snap_adapter", ["snap"])
    return monkeypatch


def test_is_available(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.snap_adapter", ["snap"])
    assert SnapAdapter().is_available() is True


def test_is_available_without_snap(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.snap_adapter", [])
    assert SnapAdapter().is_available() is False


def test_search_parses_table(snap_env):
    routes = [
        (["snap", "find", "--color=never", "vlc"], 0, output_samples.SNAP_FIND, ""),
    ]
    calls = patch_runner(snap_env, "ins.adapters.snap_adapter", routes)

    results = SnapAdapter().search("vlc")

    assert calls[0] == ["snap", "find", "--color=never", "vlc"]
    by_id = {r.id: r for r in results}
    assert by_id["vlc"].version == "3.0.20"
    assert by_id["vlc"].description == "VLC media player"
    assert by_id["gimp"].version == "2.10.38"
    assert by_id["gimp"].description == "GNU Image Manipulation Program"
    assert all(r.source == "snap" for r in results)


def test_search_no_match_returns_empty(snap_env):
    routes = [
        (["snap", "find", "--color=never", "zzz"],
         output_samples.SNAP_FIND_NO_MATCH[2],
         output_samples.SNAP_FIND_NO_MATCH[0],
         output_samples.SNAP_FIND_NO_MATCH[1]),
    ]
    patch_runner(snap_env, "ins.adapters.snap_adapter", routes)

    assert SnapAdapter().search("zzz") == []


def test_list_installed_parses_table(snap_env):
    routes = [(["snap", "list"], 0, output_samples.SNAP_LIST, "")]
    calls = patch_runner(snap_env, "ins.adapters.snap_adapter", routes)

    installed = SnapAdapter().list_installed()

    assert calls[0] == ["snap", "list"]
    by_id = {i.id: i for i in installed}
    assert set(by_id) == {"vlc", "firefox"}
    assert by_id["vlc"].version == "3.0.20"
    assert all(i.installed for i in installed)


def test_install_privileged(snap_env):
    routes = [(["snap", "install", "vlc"], 0, "", "")]
    calls = patch_runner(snap_env, "ins.adapters.snap_adapter", routes)

    assert SnapAdapter().install("vlc") is True
    assert calls[0][0] in ("sudo", "pkexec")
    assert calls[0][1:] == ["snap", "install", "vlc"]


def test_remove_privileged(snap_env):
    routes = [(["snap", "remove", "vlc"], 0, "", "")]
    calls = patch_runner(snap_env, "ins.adapters.snap_adapter", routes)

    assert SnapAdapter().remove("vlc") is True
    assert calls[0][0] in ("sudo", "pkexec")
    assert calls[0][1:] == ["snap", "remove", "vlc"]


def test_install_streams_progress(snap_env):
    routes = [(["snap", "install", "vlc"], 0, "Installing vlc\nProgress: 100%\n", "")]
    patch_runner(snap_env, "ins.adapters.snap_adapter", routes)

    seen: list[str] = []
    assert SnapAdapter().install("vlc", on_progress=seen.append) is True
    assert seen == ["Installing vlc", "Progress: 100%"]


def test_update_counts_refreshed_snaps(snap_env):
    routes = [(["snap", "refresh"], 0, output_samples.SNAP_REFRESH, "")]
    calls = patch_runner(snap_env, "ins.adapters.snap_adapter", routes)

    assert SnapAdapter().update() == 2
    assert calls[0][0] in ("sudo", "pkexec")
    assert calls[0][1:] == ["snap", "refresh"]


def test_update_all_up_to_date_counts_zero(snap_env):
    routes = [(["snap", "refresh"], 0, output_samples.SNAP_REFRESH_NONE, "")]
    patch_runner(snap_env, "ins.adapters.snap_adapter", routes)

    assert SnapAdapter().update() == 0


def test_update_streams_progress(snap_env):
    routes = [(["snap", "refresh"], 0, output_samples.SNAP_REFRESH, "")]
    patch_runner(snap_env, "ins.adapters.snap_adapter", routes)

    seen: list[str] = []
    assert SnapAdapter().update(on_progress=seen.append) == 2
    assert seen == ["vlc 3.0.20 3.1.0 10 from snap-store", "firefox 130.0 131.0 5 from snap-store"]


def test_outdated_parses_refresh_list(snap_env):
    routes = [(["snap", "refresh", "--list"], 0, output_samples.SNAP_REFRESH_LIST, "")]
    calls = patch_runner(snap_env, "ins.adapters.snap_adapter", routes)

    outdated = SnapAdapter().outdated()

    assert calls[0] == ["snap", "refresh", "--list"]
    by_id = {i.id: i for i in outdated}
    assert set(by_id) == {"vlc", "firefox"}
    assert by_id["vlc"].available == "3.0.21"
    assert by_id["firefox"].available == "131.0"
    assert all(i.installed for i in outdated)


def test_outdated_all_up_to_date_returns_empty(snap_env):
    routes = [(["snap", "refresh", "--list"], 0, output_samples.SNAP_REFRESH_NONE, "")]
    patch_runner(snap_env, "ins.adapters.snap_adapter", routes)

    assert SnapAdapter().outdated() == []


def test_upgrade_privileged(snap_env):
    routes = [(["snap", "refresh", "vlc"], 0, "", "")]
    calls = patch_runner(snap_env, "ins.adapters.snap_adapter", routes)

    assert SnapAdapter().upgrade("vlc") is True
    assert calls[0][0] in ("sudo", "pkexec")
    assert calls[0][1:] == ["snap", "refresh", "vlc"]
