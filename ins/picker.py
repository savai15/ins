"""Interactive type-to-filter picker: bare `ins` opens it on a terminal.

Key handling is pluggable so tests can script key sequences; on a real
terminal `_default_key_reader` uses raw mode (POSIX termios / Windows msvcrt).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Callable, Iterator

from rich.console import Console
from rich.live import Live
from rich.table import Table

from ins import theme
from ins.search_engine import GroupedResult, NoSourcesError, SearchEngine

Key = tuple

_CAPTION = "type to filter · ↑/↓ move · enter install · ctrl-c quit"


@dataclass
class PickerState:
    """Type-to-filter query state and selection over live search results."""

    engine: SearchEngine
    query: str = ""
    results: list = field(default_factory=list)
    selected: int = 0

    def refine(self) -> None:
        try:
            self.results = self.engine.search(self.query) if self.query else []
        except NoSourcesError:
            self.results = []
        self.selected = 0

    def move(self, delta: int) -> None:
        if not self.results:
            return
        self.selected = (self.selected + delta) % len(self.results)

    def apply(self, key: Key) -> bool:
        """Apply one key; returns True when the loop should end."""
        kind = key[0]
        if kind == "char":
            self.query += key[1]
            self.refine()
        elif kind == "backspace":
            self.query = self.query[:-1]
            self.refine()
        elif kind == "up":
            self.move(-1)
        elif kind == "down":
            self.move(1)
        elif kind in ("enter", "cancel"):
            return True
        return False


def _render_table(state: PickerState) -> Table:
    table = Table(
        box=None,
        header_style="bold",
        pad_edge=False,
        collapse_padding=True,
        caption=_CAPTION,
    )
    if not state.results:
        table.add_column("Prompt")
        table.add_row(f"[dim]search: {state.query or 'start typing…'}[/dim]")
        return table
    table.add_column("Package", min_width=24)
    table.add_column("Description", style=theme.DIM, overflow="fold")
    for idx, group in enumerate(state.results):
        marker = "▸ " if idx == state.selected else "  "
        cell = f"{marker}[bold]{group.name}[/bold]"
        if group.primary.version:
            cell += f" [dim]{group.primary.version}[/dim]"
        if group.any_installed:
            cell += f" [{theme.SUCCESS}]\\[installed][/]"
        desc = ""
        if group.primary.description:
            desc = group.primary.description.splitlines()[0]
        table.add_row(cell, desc)
    return table


def select_package(
    engine: SearchEngine,
    console: Console,
    key_reader: Callable[[], Iterator[Key]] | None = None,
) -> GroupedResult | None:
    """Run the picker loop; return the selected result, or None on cancel."""
    keys = key_reader() if key_reader is not None else _default_key_reader()
    state = PickerState(engine)
    choice: GroupedResult | None = None
    with Live(console=console) as live:
        live.update(_render_table(state), refresh=True)
        for key in keys:
            ended = state.apply(key)
            live.update(_render_table(state), refresh=True)
            if ended:
                if key[0] == "enter" and state.results:
                    choice = state.results[state.selected]
                break
    return choice


def _default_key_reader() -> Iterator[Key]:
    """Read keys from the terminal until enter/cancel is pressed."""
    if os.name == "nt":
        import msvcrt

        arrows = {"H": ("up",), "P": ("down",), "K": ("left",), "M": ("right",)}
        while True:
            ch = msvcrt.getwch()
            if ch in ("\r", "\n"):
                yield ("enter",)
            elif ch in ("\x08", "\x7f"):
                yield ("backspace",)
            elif ch == "\x03":
                yield ("cancel",)
            elif ch in ("\xe0", "\x00"):
                yield arrows.get(msvcrt.getwch(), ("cancel",))
            elif ch == "\x1b":
                yield ("cancel",)
            elif ch.isprintable():
                yield ("char", ch)
    else:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = os.read(fd, 1)
                if ch == b"\x1b":
                    seq = os.read(fd, 2)
                    if seq == b"[A":
                        yield ("up",)
                    elif seq == b"[B":
                        yield ("down",)
                    else:
                        yield ("cancel",)
                elif ch in (b"\r", b"\n"):
                    yield ("enter",)
                elif ch in (b"\x7f", b"\x08"):
                    yield ("backspace",)
                elif ch in (b"\x03", b"\x04"):
                    yield ("cancel",)
                else:
                    try:
                        yield ("char", ch.decode("utf-8"))
                    except UnicodeDecodeError:
                        pass
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
