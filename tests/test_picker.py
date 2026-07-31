"""Interactive picker tests: state machine, scripted key sequences, CLI wiring."""

from __future__ import annotations

import io

from ins.picker import PickerState, select_package
from ins.search_engine import SearchEngine
from rich.console import Console


def _console() -> Console:
    return Console(file=io.StringIO(), width=120)


def test_state_filters_as_you_type(fake_pair):
    state = PickerState(SearchEngine(fake_pair))
    assert state.results == []
    state.apply(("char", "v"))
    state.apply(("char", "l"))
    state.apply(("char", "c"))
    assert state.query == "vlc"
    names = [g.name for g in state.results]
    assert "vlc" in names
    assert all("vlc" in n for n in names)


def test_state_backspace_clears_query(fake_pair):
    state = PickerState(SearchEngine(fake_pair))
    state.apply(("char", "v"))
    state.apply(("char", "l"))
    state.apply(("backspace",))
    assert state.query == "v"


def test_state_arrow_wrap(fake_pair):
    state = PickerState(SearchEngine(fake_pair))
    state.results = [object(), object(), object()]
    state.selected = 0
    state.move(-1)
    assert state.selected == 2
    state.move(1)
    assert state.selected == 0
    state.apply(("down",))
    assert state.selected == 1


def test_select_package_returns_selected(fake_pair):
    engine = SearchEngine(fake_pair)
    keys = [("char", "v"), ("char", "l"), ("char", "c"), ("enter",)]
    choice = select_package(engine, _console(), key_reader=lambda: iter(keys))
    assert choice is not None
    assert choice.name == "vlc"


def test_select_package_cancel_returns_none(fake_pair):
    engine = SearchEngine(fake_pair)
    keys = [("char", "v"), ("cancel",)]
    assert select_package(engine, _console(), key_reader=lambda: iter(keys)) is None


def test_select_package_enter_without_results_returns_none(fake_pair):
    engine = SearchEngine(fake_pair)
    keys = [("char", "z"), ("char", "z"), ("enter",)]
    assert select_package(engine, _console(), key_reader=lambda: iter(keys)) is None


def test_select_package_backspace_recover(fake_pair):
    engine = SearchEngine(fake_pair)
    keys = [("char", "z"), ("backspace",), ("char", "v"), ("enter",)]
    choice = select_package(engine, _console(), key_reader=lambda: iter(keys))
    assert choice is not None
    assert choice.name == "vlc"


def test_bare_ins_runs_picker_on_tty(fake_env, capsys, monkeypatch):
    from ins import cli

    monkeypatch.setattr("ins.cli._stdin_is_tty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")

    def fake_select(engine, console):
        from ins.search_engine import SearchEngine as SE

        assert isinstance(engine, SE)
        return engine.search("vlc")[0]

    monkeypatch.setattr("ins.cli.select_package", fake_select)

    rc = cli.main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "press enter to install" in out
    assert "skipped vlc" in out


def test_bare_ins_picker_install_flow(fake_env, capsys, monkeypatch, tmp_path):
    from ins import cli
    from ins.cache import Cache

    monkeypatch.setattr("ins.cli._stdin_is_tty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    monkeypatch.setattr("ins.cli.select_package", lambda engine, console: engine.search("vlc")[0])

    rc = cli.main([])
    out = capsys.readouterr().out

    assert rc == 0
    assert "installed vlc from fake" in out
    assert Cache(tmp_path / "cache.db").get_installed("fake") == [("fake", "vlc", "3.0.20")]


def test_bare_ins_cancel(fake_env, capsys, monkeypatch):
    from ins import cli

    monkeypatch.setattr("ins.cli._stdin_is_tty", lambda: True)
    monkeypatch.setattr("ins.cli.select_package", lambda engine, console: None)

    rc = cli.main([])
    assert rc == 0
