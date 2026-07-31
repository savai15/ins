"""Part 9 tests: `ins info <pkg>` detail view."""

from __future__ import annotations

from ins import cli
from ins.adapters.dnf_adapter import DnfAdapter
from ins.adapters.pacman_adapter import PacmanAdapter
from ins.adapters.snap_adapter import SnapAdapter
from ins.adapters.zypper_adapter import ZypperAdapter

from conftest import patch_runner, patch_which


def test_info_shows_detail_view(fake_env, capsys):
    rc = cli.main(["info", "vlc"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "vlc" in out
    assert "3.0.20" in out
    assert "GPL-2.0" in out
    assert "https://example.org/apps/vlc" in out
    assert "not installed" in out


def test_info_shows_installed_state(fake_env, capsys):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    rc = cli.main(["info", "vlc"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "installed" in out


def test_info_not_found(fake_env, capsys):
    rc = cli.main(["info", "zzz-not-here"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "not found" in err


def test_info_requires_subject(fake_env, capsys):
    rc = cli.main(["info"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "requires a package name" in err


def test_info_fuzzy_finds_close_name(fake_env, capsys):
    rc = cli.main(["info", "vcl"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "vlc" in out


# ------------------------------------------------------ per-adapter info parses

def test_dnf_info_parses_fields(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.dnf_adapter", ["dnf"])
    routes = [
        (
            ["dnf", "info", "vlc"], 0,
            (
                "Name         : vlc\nVersion      : 3.0.20\n"
                "License      : GPL-2.0-or-later\nURL          : https://www.videolan.org/\n"
                "Description  : The portable version of VLC media player\n"
                "               with extra long text\n"
            ),
            "",
        ),
    ]
    patch_runner(monkeypatch, "ins.adapters.dnf_adapter", routes)

    extra = DnfAdapter().info("vlc")
    assert extra["license"] == "GPL-2.0-or-later"
    assert extra["homepage"] == "https://www.videolan.org/"
    assert "with extra long text" in extra["description"]


def test_pacman_info_parses_fields(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.pacman_adapter", ["pacman"])
    routes = [
        (
            ["pacman", "-Si", "vlc"], 0,
            (
                "Name            : vlc\nVersion         : 3.0.20-2\n"
                "URL             : https://www.videolan.org/\nLicenses        : GPL-2.0\n"
                "Description     : Multi-platform multimedia player\n"
            ),
            "",
        ),
    ]
    patch_runner(monkeypatch, "ins.adapters.pacman_adapter", routes)

    extra = PacmanAdapter().info("vlc")
    assert extra["license"] == "GPL-2.0"
    assert extra["homepage"] == "https://www.videolan.org/"
    assert "Multi-platform" in extra["description"]


def test_zypper_info_parses_license(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.zypper_adapter", ["zypper"])
    routes = [
        (
            ["zypper", "-n", "info", "vlc"], 0,
            (
                "Information for package vlc:\n-----------------------------\n"
                "Repository     : packman\nName           : vlc\n"
                "License        : GPL-2.0+\n"
            ),
            "",
        ),
    ]
    patch_runner(monkeypatch, "ins.adapters.zypper_adapter", routes)

    assert ZypperAdapter().info("vlc") == {"license": "GPL-2.0+"}


def test_snap_info_parses_license_and_skips_unset(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.snap_adapter", ["snap"])
    routes = [
        (["snap", "info", "vlc"], 0,
         "name:      vlc\nsummary:   VLC media player\nlicense:   GPL-2.0\n", ""),
        (["snap", "info", "foo"], 0, "name: foo\nlicense: unset\n", ""),
    ]
    patch_runner(monkeypatch, "ins.adapters.snap_adapter", routes)

    assert SnapAdapter().info("vlc")["license"] == "GPL-2.0"
    assert SnapAdapter().info("foo") is None


def test_adapters_without_info_return_none(fake_pair):
    for adapter in fake_pair:
        assert adapter.info("anything") is None or isinstance(adapter.info("anything"), dict)


def test_info_missing_details_render_dash(fake_env, capsys):
    from io import StringIO

    from ins.models import AppInfo
    from ins.renderer import render_info
    from ins.search_engine import GroupedResult
    from rich.console import Console

    group = GroupedResult(
        key="x", name="x",
        primary=AppInfo(id="x", name="x", source="fake", description="desc"),
    )
    console = Console(file=StringIO(), width=120)
    render_info(console, group, {})
    assert "—" in console.file.getvalue()
