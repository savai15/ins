"""CLI tests: end-to-end flows against the private fake adapters."""

from __future__ import annotations

from ins import cli
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


def test_bare_ins_shows_command_list(fake_env, capsys):
    rc = cli.main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert "--search" in captured.out
    assert "doctor" in captured.out
    assert "bundle install <file>" in captured.out
    assert captured.err == ""


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


def test_export_writes_manifest_file(fake_env, capsys, tmp_path):
    cli.main(["-i", "vlc", "git", "-y"])
    capsys.readouterr()

    manifest = tmp_path / "manifest.toml"
    rc = cli.main(["export", str(manifest)])
    out = capsys.readouterr().out

    assert rc == 0
    assert "exported 2 package(s)" in out
    import tomllib

    with open(manifest, "rb") as fh:
        data = tomllib.load(fh)
    assert data["packages"]["fake"]["vlc"] == "3.0.20"
    assert data["packages"]["fake"]["git"] == "2.45.2"


def test_export_prints_to_stdout(fake_env, capsys, tmp_path):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()

    rc = cli.main(["export"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "[packages.fake]" in out
    assert 'vlc = "3.0.20"' in out


def test_export_unwritable_target_fails_cleanly(fake_env, capsys, tmp_path):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()

    target = tmp_path / "no-such-dir" / "manifest.toml"
    rc = cli.main(["export", str(target)])
    err = capsys.readouterr().err

    assert rc == 1
    assert "could not write" in err
    assert not target.exists()


def test_bundle_check_up_to_date(fake_env, capsys, tmp_path):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    manifest = tmp_path / "m.toml"
    cli.main(["export", str(manifest)])
    capsys.readouterr()

    rc = cli.main(["bundle", "check", str(manifest)])
    out = capsys.readouterr().out

    assert rc == 0
    assert "bundle is up to date" in out


def test_bundle_check_reports_missing(fake_env, capsys, tmp_path):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    manifest = tmp_path / "m.toml"
    cli.main(["export", str(manifest)])
    capsys.readouterr()
    cli.main(["-r", "vlc", "-y"])
    capsys.readouterr()

    rc = cli.main(["bundle", "check", str(manifest)])
    out = capsys.readouterr().out

    assert rc == 1
    assert "vlc missing (fake)" in out


def test_bundle_check_reports_version_mismatch(fake_env, capsys, tmp_path):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    manifest = tmp_path / "m.toml"
    manifest.write_text('[packages.fake]\nvlc = "9.9.9"\n', encoding="utf-8")

    rc = cli.main(["bundle", "check", str(manifest)])
    out = capsys.readouterr().out

    assert rc == 1
    assert "manifest requires 9.9.9" in out


def test_bundle_check_json(fake_env, capsys, tmp_path):
    import json as _json

    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    manifest = tmp_path / "m.toml"
    manifest.write_text('[packages.fake]\nvlc = "9.9.9"\nhtop = "3.3.0"\n', encoding="utf-8")

    rc = cli.main(["bundle", "check", str(manifest), "--json"])
    payload = _json.loads(capsys.readouterr().out)

    assert rc == 1
    assert payload["missing"] == [["fake", "htop"]]
    assert payload["mismatched"] == [
        {"source": "fake", "package": "vlc", "installed": "3.0.20", "required": "9.9.9"}
    ]


def test_bundle_install_applies_manifest(fake_env, capsys, tmp_path):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    manifest = tmp_path / "m.toml"
    manifest.write_text('[packages.fake]\nvlc = "3.0.20"\nhtop = "3.3.0"\n', encoding="utf-8")

    rc = cli.main(["bundle", "install", str(manifest), "-y"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "installed htop from fake" in out
    assert "up to date" not in out
    installed = set(Cache(tmp_path / "cache.db").get_installed("fake"))
    assert installed == {("fake", "vlc", "3.0.20"), ("fake", "htop", "")}


def test_bundle_install_up_to_date(fake_env, capsys, tmp_path):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    manifest = tmp_path / "m.toml"
    cli.main(["export", str(manifest)])
    capsys.readouterr()

    rc = cli.main(["bundle", "install", str(manifest), "-y"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "bundle is up to date" in out


def test_bundle_install_unknown_source_fails(fake_env, capsys, tmp_path):
    manifest = tmp_path / "m.toml"
    manifest.write_text('[packages.apt]\nvlc = "3.0.20"\n', encoding="utf-8")

    rc = cli.main(["bundle", "install", str(manifest), "-y"])
    err = capsys.readouterr().err

    assert rc == 1
    assert "source 'apt' is not available" in err


def test_bundle_missing_file(fake_env, capsys, tmp_path):
    rc = cli.main(["bundle", "check", str(tmp_path / "nope.toml")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "manifest not found" in err


def test_bundle_invalid_toml(fake_env, capsys, tmp_path):
    manifest = tmp_path / "m.toml"
    manifest.write_text("not [valid toml", encoding="utf-8")

    rc = cli.main(["bundle", "check", str(manifest)])
    err = capsys.readouterr().err

    assert rc == 2
    assert "invalid manifest" in err


def test_bundle_requires_file(fake_env, capsys):
    rc = cli.main(["bundle", "check"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "requires a manifest file" in err


def test_bundle_unknown_action(fake_env, capsys):
    rc = cli.main(["bundle", "frobnicate", "x.toml"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "check|install" in err


def test_install_dry_run_changes_nothing(fake_env, capsys, tmp_path):
    rc = cli.main(["-i", "vlc", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "would install vlc from fake" in out
    assert "24.3 MB" in out
    assert Cache(tmp_path / "cache.db").get_installed("fake") == []


def test_install_dry_run_unknown_package(fake_env, capsys):
    rc = cli.main(["-i", "zzz-not-here", "--dry-run"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "not found" in err


def test_install_dry_run_already_installed(fake_env, capsys, tmp_path):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    rc = cli.main(["-i", "vlc", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "already installed" in out
    assert Cache(tmp_path / "cache.db").get_installed("fake") == [("fake", "vlc", "3.0.20")]


def test_install_dry_run_json(fake_env, capsys):
    import json as _json

    rc = cli.main(["-i", "vlc", "--dry-run", "--json"])
    payload = _json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["dry_run"] is True
    assert payload["action"] == "install"
    assert payload["packages"] == [
        {"name": "vlc", "source": "fake", "version": "3.0.20", "size": 25432064, "installed": False}
    ]


def test_remove_dry_run_changes_nothing(fake_env, capsys, tmp_path):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    rc = cli.main(["-r", "vlc", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "would remove vlc from fake (3.0.20)" in out
    assert Cache(tmp_path / "cache.db").get_installed("fake") == [("fake", "vlc", "3.0.20")]


def test_remove_dry_run_not_installed(fake_env, capsys):
    rc = cli.main(["-r", "vlc", "--dry-run"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "not installed" in err


def test_update_dry_run_lists_counts(fake_env, capsys):
    rc = cli.main(["-u", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "fake: up to date" in out
    assert "fake2: up to date" in out


def test_update_dry_run_counts_outdated(fake_env, capsys):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    rc = cli.main(["-u", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "would update 1 package(s) via fake" in out


def test_update_dry_run_json(fake_env, capsys):
    import json as _json

    rc = cli.main(["-u", "--dry-run", "--json"])
    payload = _json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["dry_run"] is True
    assert payload["action"] == "update"
    assert payload["sources"] == {"fake": 0, "fake2": 0}


def test_upgrade_dry_run_shows_versions(fake_env, capsys):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    rc = cli.main(["-U", "vlc", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "would upgrade vlc from fake (3.0.20 -> 3.0.21)" in out


def test_upgrade_dry_run_json(fake_env, capsys):
    import json as _json

    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    rc = cli.main(["-U", "vlc", "--dry-run", "--json"])
    payload = _json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["packages"] == [
        {"name": "vlc", "source": "fake", "version": "3.0.20", "available": "3.0.21"}
    ]


def test_history_records_transactions(fake_env, capsys, tmp_path):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    cli.main(["-r", "vlc", "-y"])
    capsys.readouterr()

    rc = cli.main(["history"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "install" in out
    assert "remove" in out
    assert "vlc" in out
    assert "fake" in out


def test_history_empty(fake_env, capsys):
    rc = cli.main(["history"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no transactions recorded yet" in out


def test_history_limit(fake_env, capsys):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    rc = cli.main(["history", "1"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "install" in out
    assert "remove" not in out


def test_history_invalid_size(fake_env, capsys):
    rc = cli.main(["history", "abc"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "invalid history size" in err


def test_history_json(fake_env, capsys):
    import json as _json

    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()

    rc = cli.main(["history", "--json"])
    payload = _json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["history"][0]["action"] == "install"
    assert payload["history"][0]["package"] == "vlc"
    assert payload["history"][0]["version"] == "3.0.20"


def test_undo_removes_last_install(fake_env, capsys, tmp_path):
    cli.main(["-i", "vlc", "git", "-y"])
    capsys.readouterr()

    rc = cli.main(["undo", "-y"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "undid install of git from fake" in out
    installed = set(Cache(tmp_path / "cache.db").get_installed("fake"))
    assert installed == {("fake", "vlc", "3.0.20")}


def test_undo_reinstalls_last_remove(fake_env, capsys, tmp_path):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    cli.main(["-r", "vlc", "-y"])
    capsys.readouterr()

    rc = cli.main(["undo", "-y"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "undid remove of vlc from fake" in out
    assert Cache(tmp_path / "cache.db").get_installed("fake") == [("fake", "vlc", "3.0.20")]


def test_undo_guards_install_state_change(fake_env, capsys):
    from fake_adapter import FakeAdapter

    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    FakeAdapter("fake").remove("vlc")

    rc = cli.main(["undo", "-y"])
    err = capsys.readouterr().err

    assert rc == 1
    assert "cannot undo: 'vlc' is no longer installed" in err


def test_undo_guards_remove_state_change(fake_env, capsys):
    from fake_adapter import FakeAdapter

    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    cli.main(["-r", "vlc", "-y"])
    capsys.readouterr()
    FakeAdapter("fake").install("vlc")

    rc = cli.main(["undo", "-y"])
    err = capsys.readouterr().err

    assert rc == 1
    assert "cannot undo: 'vlc' is still installed" in err


def test_undo_nothing_to_undo(fake_env, capsys):
    rc = cli.main(["undo"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "nothing to undo" in out


def test_undo_confirm_denied(fake_env, capsys, monkeypatch, tmp_path):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    monkeypatch.setattr("builtins.input", lambda prompt: "n")

    rc = cli.main(["undo"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "skipped" in out
    assert Cache(tmp_path / "cache.db").get_installed("fake") == [("fake", "vlc", "3.0.20")]


def test_quiet_suppresses_success_messages(fake_env, capsys):
    rc = cli.main(["-i", "vlc", "-y", "-q"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out == ""


def test_quiet_keeps_errors(fake_env, capsys):
    rc = cli.main(["-i", "zzz-not-here", "-y", "-q"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "not found" in err


def test_no_progress_still_installs(fake_env, capsys, tmp_path):
    rc = cli.main(["-i", "vlc", "-y", "--no-progress"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "installed vlc from fake" in out
    assert Cache(tmp_path / "cache.db").get_installed("fake") == [("fake", "vlc", "3.0.20")]


def test_doctor_json(fake_env, capsys):
    import json as _json

    from fake_adapter import FakeAdapter

    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()
    FakeAdapter("fake2").install("vlc")

    rc = cli.main(["doctor", "--json"])
    payload = _json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["duplicates"][0]["name"] == "vlc"
    assert set(payload["duplicates"][0]["sources"]) == {"fake", "fake2"}
    assert payload["sources"]["detected"] == ["fake", "fake2"]


def test_update_json(fake_env, capsys):
    import json as _json

    rc = cli.main(["-u", "--json"])
    payload = _json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["total"] == 6
    assert payload["sources"] == {"fake": 3, "fake2": 3}
    assert payload["updaters"] == {}
    assert payload["failed"] == []


def _web_stub(monkeypatch, *names, error=None):
    """Stub ins.web._http_get so CLI tests never touch the real network."""
    import json as _json

    from ins import web

    def stub(url, *, timeout, token=""):
        if error:
            raise web.WebError(error)
        items = [
            {
                "full_name": f"owner/{n}",
                "name": n,
                "description": f"{n} description",
                "html_url": f"https://github.com/owner/{n}",
                "stargazers_count": 42,
            }
            for n in names
        ]
        return _json.dumps({"total_count": len(names), "items": items}).encode()

    monkeypatch.setattr(web, "_http_get", stub)


def _inputs(monkeypatch, *answers):
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda *a: next(it))


# ---------------------------------------------------------------- web search


def test_web_flag_requires_search(fake_env, capsys):
    rc = cli.main(["-w"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "require a search" in err


def test_paging_requires_search(fake_env, capsys):
    rc = cli.main(["--page", "2"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "require a search" in err


def test_web_renders_github_repos(fake_env, capsys, monkeypatch):
    _web_stub(monkeypatch, "opencode", "freebuf")
    rc = cli.main(["-s", "opencode", "-w", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "opencode [web]" in out
    assert "freebuf [web]" in out
    assert "opencode description" in out


def test_web_json_shape(fake_env, capsys, monkeypatch):
    import json as _json

    _web_stub(monkeypatch, "opencode")
    rc = cli.main(["-s", "opencode", "-w", "--json", "--source", "web"])
    payload = _json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["web"] == [
        {
            "name": "opencode",
            "repo": "owner/opencode",
            "url": "https://github.com/owner/opencode",
            "description": "opencode description",
            "stars": 42,
        }
    ]
    assert payload["page"] == 1
    assert payload["per_page"] == 20
    assert payload["total"] == 1


def test_web_only_source_needs_no_local_adapters(fake_env, capsys, monkeypatch):
    _web_stub(monkeypatch, "opencode")
    rc = cli.main(["-s", "opencode", "-w", "--source", "web", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no package sources detected" not in out
    assert "opencode [web]" in out


def test_web_disabled_in_config(fake_env, capsys, monkeypatch):
    from ins.config import Config

    cfg = Config()
    cfg.web.enabled = False
    monkeypatch.setattr(cli.Config, "load", lambda *a, **kw: cfg)
    rc = cli.main(["-s", "vlc", "-w"])
    err = capsys.readouterr().err
    assert rc == 0
    assert "web search is disabled" in err


def test_web_network_error_degrades_to_local(fake_env, capsys, monkeypatch):
    _web_stub(monkeypatch, error="rate limited")
    rc = cli.main(["-s", "vlc", "-w"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "web search unavailable" in out
    assert "vlc [fake]" in out  # local results still shown


# ---------------------------------------------------------------- web install


def test_web_install_with_yes_runs_recipe(fake_env, capsys, monkeypatch):
    ran: list[str] = []
    _web_stub(monkeypatch, "opencode")

    def fake_run(plan):
        ran.append(plan.display)

    monkeypatch.setattr(cli, "_run_web_command", fake_run)
    rc = cli.main(["-s", "opencode", "-w", "-y", "--source", "web"])
    out = capsys.readouterr().out
    assert rc == 0
    assert ran == ["curl -fsSL https://opencode.ai/install | bash"]
    assert "✓ installed opencode (web)" in out


def test_web_install_run_requires_second_confirm(fake_env, capsys, monkeypatch):
    ran: list[str] = []
    _web_stub(monkeypatch, "opencode")

    def fake_run(plan):
        ran.append(plan.display)

    monkeypatch.setattr(cli, "_run_web_command", fake_run)
    _inputs(monkeypatch, "y", "n")  # install yes, then decline the run
    rc = cli.main(["-s", "opencode", "-w", "--source", "web"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Plan: curl -fsSL https://opencode.ai/install | bash" in out
    assert "skipped opencode" in out
    assert ran == []  # never executed


def test_web_install_records_history(fake_env, capsys, monkeypatch):
    import json as _json

    _web_stub(monkeypatch, "opencode")
    monkeypatch.setattr(cli, "_run_web_command", lambda plan: None)
    rc = cli.main(["-s", "opencode", "-w", "-y", "--source", "web"])
    capsys.readouterr()
    assert rc == 0

    rc = cli.main(["history", "--json"])
    payload = _json.loads(capsys.readouterr().out)
    assert rc == 0
    assert any(
        r.get("action") == "install" and r.get("source") == "web" and r.get("package") == "opencode"
        for r in payload["history"]
    )


# ---------------------------------------------------------------- paging


def test_paging_page_two_slices_local(fake_env, capsys):
    import json as _json

    rc = cli.main(["-s", "i", "--per-page", "2", "--page", "2", "--json"])
    payload = _json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["page"] == 2
    assert payload["per_page"] == 2
    assert payload["total"] == 9
    assert [r["name"] for r in payload["results"]] == ["firefox", "neovim"]


def test_paging_per_page_clamped_to_max(fake_env, capsys):
    import json as _json

    rc = cli.main(["-s", "i", "--per-page", "100", "--json"])
    payload = _json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["per_page"] == 20
    assert len(payload["results"]) <= 20


def test_paging_header_rendered(fake_env, capsys):
    rc = cli.main(["-s", "i", "--per-page", "3"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "page 1 of 3" in out
    assert "showing 3 of 9 results" in out


def test_interactive_paging_next_page(fake_env, capsys, monkeypatch):
    _inputs(monkeypatch, "y", "n")
    rc = cli.main(["-s", "i", "--per-page", "2"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "page 1 of 5" in out
    assert "page 2 of 5" in out
