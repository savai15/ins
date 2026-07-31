"""Bundle manifest logic tests: export shape, round trip, drift detection."""

from __future__ import annotations

import tomllib

import pytest

from ins.bundle import build_manifest, check, dumps, load_manifest
from ins.models import AppInfo


def _app(source: str, pkg: str, version: str = "1.0") -> AppInfo:
    return AppInfo(id=pkg, name=pkg, source=source, version=version, installed=True)


def test_build_manifest_groups_by_source():
    manifest = build_manifest(
        [_app("apt", "vlc", "3.0.20-1"), _app("apt", "git", "2.45.2"), _app("flatpak", "org.videolan.VLC", "3.0.20")]
    )
    assert manifest["packages"] == {
        "apt": {"vlc": "3.0.20-1", "git": "2.45.2"},
        "flatpak": {"org.videolan.VLC": "3.0.20"},
    }


def test_manifest_round_trips_through_toml(tmp_path):
    path = tmp_path / "m.toml"
    path.write_text(dumps([_app("apt", "vlc", "3.0.20-1")]), encoding="utf-8")

    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    assert data["packages"]["apt"]["vlc"] == "3.0.20-1"
    assert load_manifest(path) == {"apt": {"vlc": "3.0.20-1"}}


def test_check_reports_missing_and_mismatch_and_extra():
    manifest = {"apt": {"vlc": "3.0.20-1", "htop": "3.3.0"}, "flatpak": {"org.videolan.VLC": "3.0.20"}}
    installed = [
        _app("apt", "vlc", "3.0.19"),
        _app("apt", "git", "2.45.2"),
        _app("snap", "vlc", "3.0.20"),
    ]
    report = check(manifest, installed)
    assert report["missing"] == [("apt", "htop"), ("flatpak", "org.videolan.VLC")]
    assert report["mismatched"] == [("apt", "vlc", "3.0.19", "3.0.20-1")]
    assert report["extra"] == [("apt", "git"), ("snap", "vlc")]


def test_check_up_to_date_when_versions_match():
    manifest = {"apt": {"vlc": "3.0.20-1"}}
    assert check(manifest, [_app("apt", "vlc", "3.0.20-1")]) == {
        "missing": [],
        "mismatched": [],
        "extra": [],
    }


def test_check_ignores_unknown_version_wants_and_unknown_installed():
    manifest = {"apt": {"vlc": "", "git": "1"}}
    installed = [_app("apt", "vlc", "3.0.20-1")]
    report = check(manifest, installed)
    assert report["missing"] == [("apt", "git")]
    assert report["mismatched"] == []


def test_load_manifest_missing_packages_section(tmp_path):
    path = tmp_path / "m.toml"
    path.write_text("ins = '0.1.0'\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_manifest(path)
