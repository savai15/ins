"""Pacman adapter (Arch Linux)."""

from __future__ import annotations

import shutil

from ins.adapters._subprocess import CommandFailed, check_rc, run, run_privileged, run_privileged_stream
from ins.adapters.base import SourceAdapter
from ins.models import AppInfo

_SEARCH_TIMEOUT = 60.0


class PacmanAdapter(SourceAdapter):
    name = "pacman"
    priority = 40

    def is_available(self) -> bool:
        return shutil.which("pacman") is not None

    def search(self, query: str, limit: int = 25) -> list[AppInfo]:
        proc = run(["pacman", "-Ss", query], timeout=_SEARCH_TIMEOUT, check=False)
        if proc.returncode == 1:
            return []
        check_rc(proc, ["pacman", "-Ss", query], allowed=(0, 1))
        installed = self._installed_names()
        lines = proc.stdout.splitlines()
        out: list[AppInfo] = []
        i = 0
        while i < len(lines) and len(out) < limit:
            line = lines[i]
            if not line.strip() or line[:1] in (" ", "\t"):
                i += 1
                continue
            parts = line.split()
            head = parts[0] if parts else ""
            if "/" in head:
                name = head.partition("/")[2]
            else:
                name = head
            version = parts[1] if len(parts) > 1 else ""
            description = ""
            if i + 1 < len(lines) and lines[i + 1][:1] in (" ", "\t"):
                description = lines[i + 1].strip()
            out.append(
                AppInfo(
                    id=name,
                    name=name,
                    description=description,
                    source=self.name,
                    version=version,
                    installed=name in installed,
                )
            )
            i += 1
        return out

    def _installed_names(self) -> set[str]:
        try:
            proc = run(["pacman", "-Q"], timeout=_SEARCH_TIMEOUT)
        except CommandFailed:
            return set()
        names: set[str] = set()
        for line in proc.stdout.splitlines():
            name = line.split("\t")[0].strip() if "\t" in line else line.split()[0].strip()
            if name:
                names.add(name)
        return names

    def list_installed(self) -> list[AppInfo]:
        proc = run(["pacman", "-Q"], timeout=_SEARCH_TIMEOUT)
        out: list[AppInfo] = []
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            out.append(
                AppInfo(
                    id=parts[0],
                    name=parts[0],
                    source=self.name,
                    version=parts[1],
                    installed=True,
                )
            )
        return out

    def install(self, package_id: str, on_progress=None) -> bool:
        cmd = ["pacman", "-S", "--noconfirm", package_id]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return True

    def remove(self, package_id: str, on_progress=None) -> bool:
        cmd = ["pacman", "-R", "--noconfirm", package_id]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return True

    # ----------------------------------------------------------------- update

    def update(self, on_progress=None) -> int:
        cmd = ["pacman", "-Sy"]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return 0

    # ---------------------------------------------------------- outdated/upgrade

    def outdated(self) -> list[AppInfo]:
        proc = run(["pacman", "-Qu"], timeout=_SEARCH_TIMEOUT, check=False)
        if proc.returncode != 0:
            return []
        out: list[AppInfo] = []
        for line in proc.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            name = parts[0]
            if "->" in parts:
                arrow = parts.index("->")
                installed, available = parts[arrow - 1], parts[arrow + 1]
            else:
                installed, available = "", parts[1]
            out.append(
                AppInfo(
                    id=name,
                    name=name,
                    source=self.name,
                    version=installed,
                    available=available,
                    installed=True,
                )
            )
        return out

    def upgrade(self, package_id: str, on_progress=None) -> bool:
        cmd = ["pacman", "-S", "--noconfirm", package_id]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return True

    # ------------------------------------------------------------------- info

    def info(self, package_id: str) -> dict[str, str] | None:
        proc = run(["pacman", "-Si", package_id], timeout=_SEARCH_TIMEOUT, check=False)
        if proc.returncode != 0:
            return None
        extra: dict[str, str] = {}
        for line in proc.stdout.splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key == "Licenses" and value:
                extra["license"] = value
            elif key == "URL" and value:
                extra["homepage"] = value
            elif key == "Description" and value:
                extra["description"] = value
        return extra or None
