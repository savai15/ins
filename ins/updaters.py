"""Tool updaters for `ins -u`: pipx, uv, rustup, fwupd + custom commands.

Unlike package sources, updaters have no search/install/remove surface — they
only refresh something user-level (Python tool shims, Rust toolchains, device
firmware metadata) and report how many items changed. Custom updaters come
from `[updaters.custom]` in the config.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable
from typing import ClassVar

from ins.adapters._subprocess import run_privileged_stream, run_stream

ProgressCallback = Callable[[str], None]

BUILTIN_UPDATERS = ("pipx", "uv", "rustup", "fwupd")

_PIPX_UPGRADED = re.compile(r"upgraded package \S+ from \S+ to \S+")
_UV_UPGRADED = re.compile(r"^Upgraded ", re.MULTILINE)
_RUSTUP_UPDATED = re.compile(r" updated - ")


class ToolUpdater:
    """Base class: one binary, one command, a heuristic update counter."""

    name: ClassVar[str]
    binary: ClassVar[str]
    command: ClassVar[list[str]]
    privileged: ClassVar[bool] = False
    count_pattern: ClassVar[re.Pattern | None] = None

    def is_available(self) -> bool:
        return shutil.which(self.binary) is not None

    def update(self, on_progress: ProgressCallback | None = None) -> int:
        """Run the update command and count how many items changed."""
        if on_progress is None:
            on_progress = lambda _line: None
        count = 0

        def on_line(line: str) -> None:
            nonlocal count
            on_progress(line)
            if self.count_pattern is not None and self.count_pattern.search(line):
                count += 1

        if self.privileged:
            run_privileged_stream(self.command, on_line)
        else:
            run_stream(self.command, on_line)
        return count


class PipxUpdater(ToolUpdater):
    name: ClassVar[str] = "pipx"
    binary: ClassVar[str] = "pipx"
    command: ClassVar[list[str]] = ["pipx", "upgrade-all"]
    count_pattern: ClassVar[re.Pattern] = _PIPX_UPGRADED


class UvUpdater(ToolUpdater):
    name: ClassVar[str] = "uv"
    binary: ClassVar[str] = "uv"
    command: ClassVar[list[str]] = ["uv", "tool", "upgrade", "--all"]
    count_pattern: ClassVar[re.Pattern] = _UV_UPGRADED


class RustupUpdater(ToolUpdater):
    name: ClassVar[str] = "rustup"
    binary: ClassVar[str] = "rustup"
    command: ClassVar[list[str]] = ["rustup", "update"]
    count_pattern: ClassVar[re.Pattern] = _RUSTUP_UPDATED


class FwupdUpdater(ToolUpdater):
    """Refresh firmware metadata only — `fwupdmgr update` is interactive and
    can brick hardware, so it stays out of unattended `ins -u`."""

    name: ClassVar[str] = "fwupd"
    binary: ClassVar[str] = "fwupdmgr"
    command: ClassVar[list[str]] = ["fwupdmgr", "refresh"]


class CustomUpdater:
    """A user-defined updater: `name = ["cmd", "arg", ...]` in the config.

    The update count is unknown (output formats vary wildly), so `update()`
    returns 0 and the CLI reports it as "ran".
    """

    def __init__(self, name: str, command: list[str]):
        self.name = name
        self.command = command
        self.privileged = False
        self.count_pattern = None

    def is_available(self) -> bool:
        return shutil.which(self.command[0]) is not None

    def update(self, on_progress: ProgressCallback | None = None) -> int:
        if on_progress is None:
            on_progress = lambda _line: None
        run_stream(self.command, on_progress)
        return 0


_BUILTINS: dict[str, type[ToolUpdater]] = {
    cls.name: cls for cls in (PipxUpdater, UvUpdater, RustupUpdater, FwupdUpdater)
}


def detect_updaters(settings) -> list[ToolUpdater | CustomUpdater]:
    """Available updaters, honoring config: disabled builtins + custom commands.

    Config layout::

        [updaters]
        disable = ["fwupd"]
        custom = { texlive = ["tlmgr", "update", "--all"] }
    """
    out: list[ToolUpdater | CustomUpdater] = []
    for name, cls in _BUILTINS.items():
        if name in settings.disable:
            continue
        updater = cls()
        if updater.is_available():
            out.append(updater)
    for name, command in settings.custom.items():
        updater = CustomUpdater(name, command)
        if updater.is_available():
            out.append(updater)
    return out
