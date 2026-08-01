"""Part 9 tests: `ins doctor` duplicate detection and resolution."""

from __future__ import annotations

import pytest
from ins import cli
from ins.adapters.apt_adapter import AptAdapter
from ins.adapters.flatpak_adapter import FlatpakAdapter

from conftest import patch_runner, patch_which
from fake_adapter import FakeAdapter


@pytest.fixture
def dup_env(fake_env, capsys):
    cli.main(["-i", "vlc", "-y"])
    assert FakeAdapter("fake2").install("vlc") is True
    capsys.readouterr()
    return fake_env


def test_doctor_flags_duplicates(dup_env, capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    rc = cli.main(["doctor"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Duplicate installations" in out
    assert "vlc" in out
    assert "removed vlc from fake2" not in out


def test_doctor_resolves_duplicate(dup_env, capsys, monkeypatch, tmp_path):
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    rc = cli.main(["doctor"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "removed vlc from fake2" in out

    from ins.cache import Cache

    assert Cache(tmp_path / "cache.db").get_installed("fake2") == []


def test_doctor_no_duplicates(fake_env, capsys):
    rc = cli.main(["doctor"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no duplicate installations found" in out
    assert "sources:" in out
    assert "cache:" in out
    assert "config:" in out


def test_doctor_respects_yes_flag_not_auto_removing(dup_env, capsys):
    rc = cli.main(["doctor", "-y"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "removed vlc from fake2" in out


def test_doctor_dry_run_never_removes(dup_env, capsys, monkeypatch):
    rc = cli.main(["doctor", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Duplicate installations" in out
    assert "removed vlc" not in out


def test_doctor_keeps_highest_priority_source(dup_env, capsys, monkeypatch):
    from ins.adapters import registry

    original_detect = registry.detect_sources

    def reordered(config):
        adapters = original_detect(config)
        return sorted(adapters, key=lambda a: 0 if a.name == "fake2" else 1)

    monkeypatch.setattr("ins.adapters.registry.detect_sources", reordered)
    rc = cli.main(["doctor", "-y"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "removed vlc from fake" in out
    assert "removed vlc from fake2" not in out


def test_doctor_unknown_source_rejected(fake_env, capsys):
    rc = cli.main(["doctor", "--s", "bogus"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "unknown source 'bogus'" in err


def test_scan_installed_warns_on_failure(fake_env, capsys, monkeypatch):
    from ins.adapters._subprocess import AdapterError

    import fake_adapter as fa

    def boom(self):
        raise AdapterError("list failed")

    monkeypatch.setattr(fa.FakeAdapter, "list_installed", boom)
    rc = cli.main(["doctor"])
    err = capsys.readouterr().err
    assert rc == 0
    assert "warning: could not scan fake" in err


# ------------------------------------------------- snap-transition stub handling

def test_doctor_skips_snap_transition_stub(fake_env, capsys, monkeypatch):
    """Ubuntu ships apt packages (firefox, thunderbird, …) that are empty
    wrappers installing the matching snap. Doctor must not treat them as
    duplicates and must never remove the real snap copy."""

    orig = cli._is_snap_transition_stub

    def stub_check(info):
        if info.id == "firefox" and info.source == "fake2":
            return True
        return orig(info)

    monkeypatch.setattr(cli, "_is_snap_transition_stub", stub_check)
    cli.main(["-i", "firefox", "-y"])
    FakeAdapter("fake2").install("firefox")
    capsys.readouterr()
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    rc = cli.main(["doctor"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no duplicate installations found" in out
    assert "transition stub" in out
    assert "removed firefox" not in out


def test_doctor_json_reports_stubs(fake_env, capsys, monkeypatch):
    import json as _json

    orig = cli._is_snap_transition_stub

    def stub_check(info):
        if info.id == "firefox" and info.source == "fake2":
            return True
        return orig(info)

    monkeypatch.setattr(cli, "_is_snap_transition_stub", stub_check)
    cli.main(["-i", "firefox", "-y"])
    FakeAdapter("fake2").install("firefox")
    capsys.readouterr()
    rc = cli.main(["doctor", "--json"])
    payload = _json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["duplicates"] == []
    assert payload["transition_stubs"] == [
        {"name": "firefox", "version": "130.0"}
    ]


# ----------------------------------------------------- apt adapter info level
def test_apt_info_parses_homepage(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apt_adapter", ["apt-get"])
    from output_samples import APT_CACHE_SHOW

    routes = [(["apt-cache", "show", "vlc"], 0, APT_CACHE_SHOW, "")]
    patch_runner(monkeypatch, "ins.adapters.apt_adapter", routes)

    extra = AptAdapter().info("vlc")
    assert extra is not None
    assert extra["homepage"] == "https://www.videolan.org/"
    assert "VLC is the VideoLAN project's media player." in extra["description"]


def test_apt_info_unknown_package_returns_none(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apt_adapter", ["apt-get"])
    routes = [(["apt-cache", "show", "missing"], 100, "", "N: Unable to locate package missing")]
    patch_runner(monkeypatch, "ins.adapters.apt_adapter", routes)

    assert AptAdapter().info("missing") is None


def test_flatpak_info_parses_license(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.flatpak_adapter", ["flatpak"])
    routes = [
        (["flatpak", "info", "org.videolan.VLC"], 0,
         "ID: org.videolan.VLC\nLicense: GPL-2.0+\nState: active\n", ""),
    ]
    calls = patch_runner(monkeypatch, "ins.adapters.flatpak_adapter", routes)

    assert FlatpakAdapter().info("org.videolan.VLC") == {"license": "GPL-2.0+"}
    assert calls[0][0] == "flatpak"
