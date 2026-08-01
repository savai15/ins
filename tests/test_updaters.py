"""Part 11 tests: tool updaters (pipx/uv/rustup/fwupd/custom) in `ins -u`,
plus `ins completions`."""

from __future__ import annotations

import pytest
from ins import cli
from ins.adapters._subprocess import AdapterError
from ins.config import Config
from ins.updaters import (
    CustomUpdater,
    FwupdUpdater,
    PipxUpdater,
    RustupUpdater,
    UvUpdater,
    detect_updaters,
)

from conftest import patch_runner, patch_which


@pytest.fixture
def updater_env(monkeypatch, tmp_path):
    """Like `fake_env`, but without the detect_updaters stub so `ins -u`
    exercises real tool updaters — with sources pinned to the test doubles so
    nothing real is touched and no root/polkit prompt can fire."""
    from ins.adapters import registry
    from ins.cache import Cache
    from ins.config import Config

    from fake_adapter import FakeAdapter

    monkeypatch.setattr(
        "ins.cli.Cache",
        lambda enabled, max_entries=5000: Cache(tmp_path / "cache.db", enabled=enabled, max_entries=max_entries),
    )
    monkeypatch.setattr("ins.config.Config.load", lambda *a, **kw: Config())
    monkeypatch.setattr(
        registry,
        "_instances",
        lambda: [FakeAdapter("fake"), FakeAdapter("fake2")],
    )
    return tmp_path

PIPX_OUT = (
    "upgraded package black from 24.4.2 to 24.8.0\n"
    "upgraded package ruff from 0.5.7 to 0.6.2\n"
    "package vlc is already at latest version 3.0.21\n"
)
PIPX_IDLE = "all packages are already at latest version\n"

UV_OUT = "Upgraded foo v0.1.0 -> v0.2.0\n"

RUSTUP_OUT = (
    "info: syncing channel updates for 'stable-x86_64-unknown-linux-gnu'\n"
    "stable-x86_64-unknown-linux-gnu updated - rustc 1.80.1 (3f5fd8dd4 2024-08-06)\n"
)
RUSTUP_IDLE = (
    "info: syncing channel updates for 'stable-x86_64-unknown-linux-gnu'\n"
    "stable-x86_64-unknown-linux-gnu up to date - rustc 1.80.1 (3f5fd8dd4 2024-08-06)\n"
)

FWUPD_OUT = (
    "Downloading… [ -    ]\n"
    "Downloading… [    - ]\n"
    "Updating metadata… [   -  ]\n"
    "Successfully updated metadata\n"
)


# ------------------------------------------------------------ updater level

def test_pipx_counts_upgraded_packages(monkeypatch):
    patch_which(monkeypatch, "ins.updaters", ["pipx"])
    routes = [(["pipx", "upgrade-all"], 0, PIPX_OUT, "")]
    calls = patch_runner(monkeypatch, "ins.updaters", routes)

    assert PipxUpdater().update() == 2
    assert calls[0] == ["pipx", "upgrade-all"]


def test_pipx_idle_is_zero(monkeypatch):
    patch_which(monkeypatch, "ins.updaters", ["pipx"])
    routes = [(["pipx", "upgrade-all"], 0, PIPX_IDLE, "")]
    patch_runner(monkeypatch, "ins.updaters", routes)

    assert PipxUpdater().update() == 0


def test_uv_counts_upgraded(monkeypatch):
    patch_which(monkeypatch, "ins.updaters", ["uv"])
    routes = [(["uv", "tool", "upgrade", "--all"], 0, UV_OUT, "")]
    calls = patch_runner(monkeypatch, "ins.updaters", routes)

    assert UvUpdater().update() == 1
    assert calls[0] == ["uv", "tool", "upgrade", "--all"]


def test_rustup_counts_updated_toolchains(monkeypatch):
    patch_which(monkeypatch, "ins.updaters", ["rustup"])
    routes = [(["rustup", "update"], 0, RUSTUP_OUT, "")]
    patch_runner(monkeypatch, "ins.updaters", routes)

    assert RustupUpdater().update() == 1


def test_rustup_idle_is_zero(monkeypatch):
    patch_which(monkeypatch, "ins.updaters", ["rustup"])
    routes = [(["rustup", "update"], 0, RUSTUP_IDLE, "")]
    patch_runner(monkeypatch, "ins.updaters", routes)

    assert RustupUpdater().update() == 0


def test_fwupd_refreshes_metadata_only(monkeypatch):
    patch_which(monkeypatch, "ins.updaters", ["fwupdmgr"])
    routes = [(["fwupdmgr", "refresh"], 0, FWUPD_OUT, "")]
    calls = patch_runner(monkeypatch, "ins.updaters", routes)

    assert FwupdUpdater().update() == 0
    assert calls[0] == ["fwupdmgr", "refresh"]


def test_custom_updater_runs_command(monkeypatch):
    patch_which(monkeypatch, "ins.updaters", ["tlmgr"])
    routes = [(["tlmgr", "update", "--all"], 0, "[1/1] package latex updated\n", "")]
    calls = patch_runner(monkeypatch, "ins.updaters", routes)

    updater = CustomUpdater("texlive", ["tlmgr", "update", "--all"])
    assert updater.update() == 0
    assert calls[0] == ["tlmgr", "update", "--all"]


def test_custom_updater_unavailable(monkeypatch):
    patch_which(monkeypatch, "ins.updaters", [])
    updater = CustomUpdater("texlive", ["tlmgr", "update", "--all"])
    assert updater.is_available() is False


def test_updater_failure_raises_adapter_error(monkeypatch):
    patch_which(monkeypatch, "ins.updaters", ["pipx"])
    routes = [(["pipx", "upgrade-all"], 1, "", "could not reach pypi")]
    patch_runner(monkeypatch, "ins.updaters", routes)

    with pytest.raises(AdapterError):
        PipxUpdater().update()


def test_detect_updaters_available_and_enabled(monkeypatch):
    patch_which(monkeypatch, "ins.updaters", ["pipx", "uv", "rustup", "fwupdmgr"])
    found = detect_updaters(Config().updaters)
    assert [u.name for u in found] == ["pipx", "uv", "rustup"]


def test_detect_updaters_fwupd_is_opt_in(monkeypatch):
    patch_which(monkeypatch, "ins.updaters", ["pipx", "uv", "rustup", "fwupdmgr"])
    cfg = Config()
    cfg.updaters.enable = ["fwupd"]
    found = detect_updaters(cfg.updaters)
    assert [u.name for u in found] == ["fwupd"]


def test_detect_updaters_respects_disable(monkeypatch):
    patch_which(monkeypatch, "ins.updaters", ["pipx", "uv", "rustup", "fwupdmgr"])
    cfg = Config()
    cfg.updaters.disable = ["pipx", "fwupd"]
    found = detect_updaters(cfg.updaters)
    assert [u.name for u in found] == ["uv", "rustup"]


def test_detect_updaters_includes_custom(monkeypatch):
    patch_which(monkeypatch, "ins.updaters", ["tlmgr"])
    cfg = Config()
    cfg.updaters.custom = {"texlive": ["tlmgr", "update", "--all"]}
    found = detect_updaters(cfg.updaters)
    assert [u.name for u in found] == ["texlive"]


def test_detect_updaters_nothing_installed(monkeypatch):
    patch_which(monkeypatch, "ins.updaters", [])
    assert detect_updaters(Config().updaters) == []


def test_config_roundtrip_updaters(tmp_path):
    cfg = Config.from_dict(
        {
            "updaters": {
                "disable": ["fwupd"],
                "custom": {"texlive": ["tlmgr", "update", "--all"]},
            }
        }
    )
    assert cfg.updaters.disable == ["fwupd"]
    assert cfg.updaters.custom == {"texlive": ["tlmgr", "update", "--all"]}

    path = tmp_path / "config.toml"
    cfg.save(path)
    loaded = Config.load(path)
    assert loaded.updaters.disable == ["fwupd"]
    assert loaded.updaters.custom == {"texlive": ["tlmgr", "update", "--all"]}


# ---------------------------------------------------------------- CLI level

def test_update_runs_detected_updaters(updater_env, capsys, monkeypatch):
    patch_which(monkeypatch, "ins.updaters", ["pipx", "uv"])
    patch_runner(
        monkeypatch,
        "ins.updaters",
        [
            (["pipx", "upgrade-all"], 0, PIPX_OUT, ""),
            (["uv", "tool", "upgrade", "--all"], 0, UV_OUT, ""),
        ],
    )

    rc = cli.main(["-u"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "6 packages updated across fake, fake2" in out
    assert "pipx: 2 update(s)" in out
    assert "uv: 1 update(s)" in out


def test_update_updaters_idle_message(updater_env, capsys, monkeypatch):
    patch_which(monkeypatch, "ins.updaters", ["pipx"])
    patch_runner(monkeypatch, "ins.updaters", [(["pipx", "upgrade-all"], 0, PIPX_IDLE, "")])

    rc = cli.main(["-u"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "pipx: up to date" in out


def test_update_custom_updater_from_config(updater_env, capsys, monkeypatch):
    cfg = Config()
    cfg.updaters.custom = {"texlive": ["tlmgr", "update", "--all"]}
    monkeypatch.setattr("ins.config.Config.load", lambda *a, **kw: cfg)
    patch_which(monkeypatch, "ins.updaters", ["tlmgr"])
    patch_runner(monkeypatch, "ins.updaters", [(["tlmgr", "update", "--all"], 0, "done\n", "")])

    rc = cli.main(["-u"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "texlive: ran" in out


def test_update_updater_failure_raises_cli_error(updater_env, capsys, monkeypatch):
    patch_which(monkeypatch, "ins.updaters", ["pipx"])
    patch_runner(monkeypatch, "ins.updaters", [(["pipx", "upgrade-all"], 1, "", "network down")])

    rc = cli.main(["-u"])
    err = capsys.readouterr().err

    assert rc == 1
    assert "pipx" in err
    assert "network down" in err


def test_update_skips_updaters_with_source_filter(fake_env, capsys, monkeypatch):
    patch_which(monkeypatch, "ins.updaters", ["pipx"])
    calls = patch_runner(monkeypatch, "ins.updaters", [(["pipx", "upgrade-all"], 0, PIPX_OUT, "")])

    rc = cli.main(["-u", "--s", "fake"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "3 packages updated across fake" in out
    assert "pipx" not in out
    assert calls == []


def test_update_updaters_json(updater_env, capsys, monkeypatch):
    import json as _json

    patch_which(monkeypatch, "ins.updaters", ["pipx", "uv"])
    patch_runner(
        monkeypatch,
        "ins.updaters",
        [
            (["pipx", "upgrade-all"], 0, PIPX_OUT, ""),
            (["uv", "tool", "upgrade", "--all"], 0, UV_OUT, ""),
        ],
    )

    rc = cli.main(["-u", "--json"])
    payload = _json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["sources"] == {"fake": 3, "fake2": 3}
    assert payload["updaters"] == {"pipx": 2, "uv": 1}
    assert payload["failed"] == []
    assert payload["total"] == 6


def test_update_updaters_dry_run(updater_env, capsys, monkeypatch):
    import json as _json

    patch_which(monkeypatch, "ins.updaters", ["pipx"])

    rc = cli.main(["-u", "--dry-run", "--json"])
    payload = _json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["dry_run"] is True
    assert payload["sources"] == {"fake": 0, "fake2": 0, "pipx": -1}


def test_update_updaters_quiet(fake_env, capsys, monkeypatch):
    patch_which(monkeypatch, "ins.updaters", ["pipx"])
    patch_runner(monkeypatch, "ins.updaters", [(["pipx", "upgrade-all"], 0, PIPX_OUT, "")])

    rc = cli.main(["-u", "-q"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "pipx" not in out
    assert out == ""


# ------------------------------------------------- completions (ins completions)

def test_completions_bash_prints_script(fake_env, capsys):
    rc = cli.main(["completions", "bash"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "complete -F _ins_completions ins" in out


def test_completions_unsupported_shell(fake_env, capsys):
    rc = cli.main(["completions", "tcsh"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "expects bash, zsh, fish, or packages" in err


def test_completions_packages_prefix(fake_env, capsys):
    rc = cli.main(["completions", "packages", "vl"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "vlc" in out


def test_completions_packages_substring_match(fake_env, capsys):
    rc = cli.main(["completions", "packages", "vi"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "neovim" in out


def test_completions_packages_no_prefix_lists_nothing(fake_env, capsys):
    rc = cli.main(["completions", "packages"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out == ""


def test_completions_packages_installed_only(fake_env, capsys):
    cli.main(["-i", "vlc", "-y"])
    capsys.readouterr()

    rc = cli.main(["completions", "packages", "--installed"])
    out = capsys.readouterr().out

    assert rc == 0
    assert out.splitlines() == ["vlc"]
