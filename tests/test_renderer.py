"""Renderer tests: rich Table output for search results (Part 6)."""

from __future__ import annotations

import re
from io import StringIO

from rich.console import Console

from ins import theme
from ins.models import AppInfo
from ins.renderer import render_search_results
from ins.search_engine import GroupedResult

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _plain(text: str) -> str:
    return ANSI_RE.sub("", text)


def _group(
    name: str = "vlc",
    source: str = "fake",
    desc: str = "VLC media player",
    version: str = "3.0.20",
    installed: bool = False,
    also: tuple[str, ...] = ("fake2",),
    stale: bool = False,
) -> GroupedResult:
    primary = AppInfo(
        id=name, name=name, description=desc, source=source,
        version=version, installed=installed,
    )
    alts = [
        AppInfo(
            id=name, name=name, description=desc, source=s,
            version=version, installed=False,
        )
        for s in also
    ]
    return GroupedResult(key=name, name=name, primary=primary, alternatives=alts, stale=stale)


def _render(results: list[GroupedResult], terminal: bool = False) -> str:
    console = Console(
        file=StringIO(), force_terminal=terminal,
        color_system="truecolor", width=120,
    )
    render_search_results(console, "vlc", results)
    return console.file.getvalue()


def test_render_includes_core_fields():
    out = _render([_group()])
    assert "vlc" in out
    assert "[fake]" in out
    assert "3.0.20" in out
    assert "VLC media player" in out
    assert "also via: fake2" in out


def test_render_also_via_lives_in_package_cell():
    out = _render([_group()])
    package_row = next(line for line in out.splitlines() if "vlc" in line)
    assert "also via" not in package_row
    assert any("also via: fake2" in line and "vlc" not in line for line in out.splitlines())


def _ansi_truecolor(color: str) -> str:
    hex6 = color.strip("#")
    r, g, b = (int(hex6[i : i + 2], 16) for i in (0, 2, 4))
    return f"38;2;{r};{g};{b}"


def test_render_installed_tag_with_color():
    out = _render([_group(installed=True)], terminal=True)
    assert "[installed]" in out
    assert "\x1b[" in out
    assert _ansi_truecolor(theme.SUCCESS) in out


def test_render_source_tag_uses_theme_color():
    out = _render([_group()], terminal=True)
    assert _ansi_truecolor(theme.color_for_source("fake")) in out


def test_render_unknown_source_falls_back_to_lavender():
    out = _render([_group(source="weird")], terminal=True)
    assert _ansi_truecolor(theme.LAVENDER) in out


def test_render_stale_note():
    out = _render([_group(stale=True)])
    assert "(cached result — source offline)" in out


def test_render_multiline_description_keeps_first_line():
    out = _render([_group(desc="first line\nsecond line")])
    assert "first line" in out
    assert "second line" not in out


def test_render_no_also_via_without_alternatives():
    out = _render([_group(also=())])
    assert "also via" not in out


def test_render_multiple_groups_stay_aligned():
    groups = [
        _group(name="vlc", desc="VLC media player", also=("fake2",)),
        _group(name="gimp", source="fake2", desc="GNU Image Manipulation Program", also=()),
    ]
    out = _render(groups)
    rows = [_plain(ln) for ln in out.splitlines() if "[fake" in ln or "gimp" in ln]
    assert len(rows) == 2
    assert all(" [fake" in ln and "3.0.20" in ln for ln in rows)
