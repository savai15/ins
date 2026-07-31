"""Part 10 tests: `--json` machine-readable output."""

from __future__ import annotations

import json

import ins.cli as cli


def test_search_json_parses(fake_env, capsys):
    rc = cli.main(["-s", "vlc", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["query"] == "vlc"
    assert len(data["results"]) == 1
    result = data["results"][0]
    assert result["name"] == "vlc"
    assert result["source"] == "fake"
    assert result["version"] == "3.0.20"
    assert result["size"] == 25432064
    assert result["installed"] is False
    assert result["also_via"] == ["fake2"]
    assert result["alternatives"][0]["source"] == "fake2"


def test_search_json_no_results(fake_env, capsys):
    rc = cli.main(["-s", "zzz-not-here", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    assert json.loads(out) == {"query": "zzz-not-here", "results": []}


def test_search_json_shows_installed_state(fake_env, capsys):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    rc = cli.main(["-s", "vlc", "--json"])
    out = capsys.readouterr().out
    assert json.loads(out)["results"][0]["installed"] is True


def test_info_json_parses(fake_env, capsys):
    rc = cli.main(["info", "vlc", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["name"] == "vlc"
    sources = {s["source"]: s for s in data["sources"]}
    assert set(sources) == {"fake", "fake2"}
    assert sources["fake"]["license"] == "GPL-2.0"
    assert sources["fake"]["homepage"] == "https://example.org/apps/vlc"
    assert sources["fake"]["version"] == "3.0.20"


def test_info_json_not_found(fake_env, capsys):
    rc = cli.main(["info", "zzz", "--json"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "not found" in err


def test_json_flag_does_not_break_install(fake_env, capsys, tmp_path):
    rc = cli.main(["-i", "vlc", "-y", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "installed vlc from fake" in out
