"""Part 7 tests: streamed progress plumbing, Progress/Live integration in CLI."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

import ins.cli as cli
from ins.adapters._subprocess import iter_stream
from ins.adapters.apt_adapter import AptAdapter
from ins.adapters.fake_adapter import FakeAdapter
from ins.adapters.flatpak_adapter import FlatpakAdapter

from conftest import apt_routes, flatpak_routes, patch_runner, patch_which


# ----------------------------------------------------------- iter_stream

def test_iter_stream_splits_on_nl_and_cr():
    fh = StringIO("Reading lists...\rUnpacking vlc (3.0.20) ...\r\nSetting up vlc\r\n\r\n")
    assert list(iter_stream(fh)) == [
        "Reading lists...",
        "Unpacking vlc (3.0.20) ...",
        "Setting up vlc",
    ]


def test_iter_stream_final_line_without_newline():
    assert list(iter_stream(StringIO("a\nb"))) == ["a", "b"]


def test_iter_stream_drops_empty_chunks():
    assert list(iter_stream(StringIO("\n\r\n\n"))) == []


# ------------------------------------------------- adapter progress routing

def test_apt_install_streams_progress_lines(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apt_adapter", ["apt-get"])
    routes = [(["apt-get"], 0, "Reading package lists...\nUnpacking vlc...\n", "")]
    calls = patch_runner(monkeypatch, "ins.adapters.apt_adapter", routes)

    seen: list[str] = []
    assert AptAdapter().install("vlc", on_progress=seen.append) is True

    assert seen == ["Reading package lists...", "Unpacking vlc..."]
    assert calls[0][0] in ("sudo", "pkexec")
    assert calls[0][1:] == ["apt-get", "-y", "install", "vlc"]


def test_apt_remove_streams_progress_lines(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apt_adapter", ["apt-get"])
    routes = [(["apt-get"], 0, "Removing vlc (3.0.20) ...\n", "")]
    patch_runner(monkeypatch, "ins.adapters.apt_adapter", routes)

    seen: list[str] = []
    assert AptAdapter().remove("vlc", on_progress=seen.append) is True
    assert seen == ["Removing vlc (3.0.20) ..."]


def test_flatpak_install_streams_without_privilege(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.flatpak_adapter", ["flatpak"])
    routes = [
        *[r for r in flatpak_routes() if r[0] != ["flatpak", "install"]],
        (["flatpak", "install", "--user", "--noninteractive", "-y", "flathub", "org.videolan.VLC"],
         0, "Installing: org.videolan.VLC\n", ""),
    ]
    calls = patch_runner(monkeypatch, "ins.adapters.flatpak_adapter", routes)

    seen: list[str] = []
    assert FlatpakAdapter().install("org.videolan.VLC", on_progress=seen.append) is True
    assert seen == ["Installing: org.videolan.VLC"]
    assert calls[-1][0] == "flatpak"


def test_fake_adapter_emits_progress_lines():
    seen: list[str] = []
    assert FakeAdapter().install("vlc", on_progress=seen.append) is True
    assert seen == ["Installing: vlc", "Done."]


# ------------------------------------------------------- CLI integration

def test_cli_passes_progress_callback_to_adapter(fake_env, capsys, monkeypatch):
    from ins.adapters import fake_adapter as fa

    captured = {}
    original = fa.FakeAdapter.install

    def spy(self, package_id, on_progress=None):
        captured["on_progress"] = on_progress
        return original(self, package_id, on_progress=on_progress)

    monkeypatch.setattr(fa.FakeAdapter, "install", spy)

    rc = cli.main(["-i", "vlc", "-y"])
    assert rc == 0
    assert callable(captured.get("on_progress"))
    captured["on_progress"]("Setting up vlc (3.0.20) ...")
    assert "installed vlc from fake" in capsys.readouterr().out


def test_cli_progress_stays_silent_when_not_a_terminal(fake_env, capsys):
    rc = cli.main(["-i", "vlc", "-y"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "\x1b[" not in out


def test_erase_animation_noop_off_terminal(fake_env, capsys, monkeypatch):
    monkeypatch.setattr(cli.time, "sleep", lambda _s: (_ for _ in ()).throw(AssertionError("slept")))
    cli._erase_animation(Console(file=StringIO()), "vlc")
    out = capsys.readouterr().out
    assert out == ""
