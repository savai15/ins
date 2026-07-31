"""CLI tests: end-to-end flows using the INS_FAKE demo adapters."""

from __future__ import annotations

import pytest

import ins.cli as cli
from ins.cache import Cache


def test_search_shows_grouped_results(fake_env, capsys):
    rc = cli.main(["-s", "vlc"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "vlc [fake]" in out
    assert "also via: fake2" in out
    assert "VLC media player" in out


def test_search_no_results(fake_env, capsys):
    rc = cli.main(["-s", "zzz-not-here"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no results found" in out


def test_search_requires_query(fake_env, capsys):
    rc = cli.main(["-s"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "requires a query" in err


def test_search_unknown_source(fake_env, capsys):
    rc = cli.main(["-s", "vlc", "--s", "bogus"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "unknown source 'bogus'" in err


def test_search_unavailable_source(fake_env, capsys):
    rc = cli.main(["-s", "vlc", "--s", "apt"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "not available on this system" in err


def test_install_with_yes(fake_env, capsys, tmp_path):
    rc = cli.main(["-i", "vlc", "-y"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "installed vlc from fake" in out

    cache = Cache(tmp_path / "cache.db")
    assert cache.get_installed("fake") == [("fake", "vlc", "3.0.20")]


def test_install_already_installed(fake_env, capsys, tmp_path):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    rc = cli.main(["-i", "vlc", "-y"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "already installed" in out


def test_install_not_found(fake_env, capsys):
    rc = cli.main(["-i", "zzz-not-here", "-y"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "not found" in err


def test_install_confirm_prompt_denied(fake_env, capsys, monkeypatch, tmp_path):
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    rc = cli.main(["-i", "vlc"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "skipped vlc" in out
    cache = Cache(tmp_path / "cache.db")
    assert cache.get_installed("fake") == []


def test_install_confirm_prompt_accepted(fake_env, capsys, monkeypatch, tmp_path):
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    rc = cli.main(["-i", "vlc"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "installed vlc" in out
    assert Cache(tmp_path / "cache.db").get_installed("fake") == [("fake", "vlc", "3.0.20")]


def test_remove_flow(fake_env, capsys, tmp_path):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    rc = cli.main(["-r", "vlc", "-y"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "removed vlc from fake" in out
    assert Cache(tmp_path / "cache.db").get_installed("fake") == []


def test_remove_not_installed(fake_env, capsys):
    rc = cli.main(["-r", "vlc", "-y"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "not installed" in err


def test_batch_install_multiple_packages(fake_env, capsys, tmp_path):
    rc = cli.main(["-i", "vlc", "git", "gimp", "-y"])
    out = capsys.readouterr().out
    assert rc == 0
    for name in ("vlc", "git", "gimp"):
        assert f"installed {name} from fake" in out
    cache = Cache(tmp_path / "cache.db")
    installed = {i.id for i in cache.list_installed()} if hasattr(cache, "list_installed") else {
        row[1] for row in cache.get_installed("fake")
    }
    assert {"vlc", "git", "gimp"} <= installed


def test_install_invalidates_cache(fake_env, capsys, tmp_path):
    cli.main(["-s", "vlc"])
    capsys.readouterr()
    cache = Cache(tmp_path / "cache.db")
    assert cache.get_any("fake", "vlc") is not None

    cli.main(["-i", "vlc", "-y"])
    assert cache.get_any("fake", "vlc") is None


def test_multiple_actions_rejected(fake_env, capsys):
    rc = cli.main(["-s", "vlc", "-i", "vlc"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "pick one action" in err


def test_update_all_sources(fake_env, capsys):
    rc = cli.main(["-u"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "packages updated across fake, fake2" in out


def test_no_action_rejected(fake_env, capsys):
    rc = cli.main([])
    err = capsys.readouterr().err
    assert rc == 2
    assert "no action given" in err


def test_list_shows_installed_grouped_by_source(fake_env, capsys, tmp_path):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()

    rc = cli.main(["-l"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "Installed packages" in out
    assert "vlc [fake]" in out
    assert "3.0.20" in out


def test_list_empty(fake_env, capsys):
    rc = cli.main(["-l"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no packages installed" in out


def test_list_json(fake_env, capsys, tmp_path):
    import json as _json

    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()

    rc = cli.main(["-l", "--json"])
    payload = _json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["installed"][0]["name"] == "vlc"
    assert payload["installed"][0]["source"] == "fake"
    assert payload["installed"][0]["version"] == "3.0.20"


def test_outdated_lists_available_versions(fake_env, capsys):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()

    rc = cli.main(["-o"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "Updates available" in out
    assert "vlc [fake]" in out
    assert "3.0.20" in out
    assert "3.0.21" in out


def test_outdated_all_up_to_date(fake_env, capsys):
    rc = cli.main(["-o"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "all packages up to date" in out


def test_outdated_json(fake_env, capsys):
    import json as _json

    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()

    rc = cli.main(["-o", "--json"])
    payload = _json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["outdated"][0]["name"] == "vlc"
    assert payload["outdated"][0]["version"] == "3.0.20"
    assert payload["outdated"][0]["available"] == "3.0.21"


def test_upgrade_installed_package(fake_env, capsys, tmp_path):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()

    rc = cli.main(["-U", "vlc", "-y"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "upgraded vlc from fake" in out
    assert Cache(tmp_path / "cache.db").get_installed("fake") == [("fake", "vlc", "")]


def test_upgrade_not_installed(fake_env, capsys):
    rc = cli.main(["-U", "vlc", "-y"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "not installed" in err


def test_upgrade_requires_package(fake_env, capsys):
    rc = cli.main(["-U"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "requires at least one package name" in err


def test_upgrade_confirm_prompt_denied(fake_env, capsys, monkeypatch, tmp_path):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    monkeypatch.setattr("builtins.input", lambda prompt: "n")

    rc = cli.main(["-U", "vlc"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "skipped vlc" in out
    assert Cache(tmp_path / "cache.db").get_installed("fake") == [("fake", "vlc", "3.0.20")]


def test_list_outdated_conflict_rejected(fake_env, capsys):
    rc = cli.main(["-l", "-o"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "pick one action" in err
