"""Zypper adapter (openSUSE)."""

from __future__ import annotations

import shutil

from ins.adapters._subprocess import run, run_privileged, run_privileged_stream
from ins.adapters.base import SourceAdapter
from ins.models import AppInfo

_SEARCH_TIMEOUT = 60.0


class ZypperAdapter(SourceAdapter):
    name = "zypper"
    priority = 50

    def is_available(self) -> bool:
        return shutil.which("zypper") is not None and shutil.which("rpm") is not None

    def search(self, query: str, limit: int = 25) -> list[AppInfo]:
        proc = run(["zypper", "-q", "search", query], timeout=_SEARCH_TIMEOUT)
        out: list[AppInfo] = []
        for line in proc.stdout.splitlines():
            if " | " not in line:
                continue
            stripped = line.strip()
            if not stripped or stripped.startswith("-"):
                continue
            if stripped.startswith(("S  ", "S |")):
                continue
            cols = [c.strip() for c in line.split("|")]
            if len(cols) < 3:
                continue
            status, name, summary = cols[0], cols[1], cols[2]
            if not name:
                continue
            out.append(
                AppInfo(
                    id=name,
                    name=name,
                    description=summary,
                    source=self.name,
                    installed=status.startswith("i"),
                )
            )
            if len(out) >= limit:
                break
        return out

    def list_installed(self) -> list[AppInfo]:
        proc = run(["rpm", "-qa", "--qf", "%{NAME}\t%{VERSION}-%{RELEASE}\n"], timeout=_SEARCH_TIMEOUT)
        out: list[AppInfo] = []
        for line in proc.stdout.splitlines():
            parts = line.split("\t")
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
        cmd = ["zypper", "-n", "install", package_id]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return True

    def remove(self, package_id: str, on_progress=None) -> bool:
        cmd = ["zypper", "-n", "remove", package_id]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return True

    # ----------------------------------------------------------------- update

    def update(self, on_progress=None) -> int:
        cmd = ["zypper", "-n", "refresh"]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return 0

    # ---------------------------------------------------------- outdated/upgrade

    def outdated(self) -> list[AppInfo]:
        proc = run(["zypper", "-q", "list-updates"], timeout=_SEARCH_TIMEOUT, check=False)
        out: list[AppInfo] = []
        for line in proc.stdout.splitlines():
            if " | " not in line:
                continue
            cols = [c.strip() for c in line.split("|")]
            if len(cols) < 7:
                continue
            status, name, installed, available = cols[0], cols[2], cols[5], cols[6]
            if not name or not status.startswith("v"):
                continue
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
        cmd = ["zypper", "-n", "update", package_id]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return True

    # ------------------------------------------------------------------- info

    def info(self, package_id: str) -> dict[str, str] | None:
        proc = run(["zypper", "-n", "info", package_id], timeout=_SEARCH_TIMEOUT, check=False)
        if proc.returncode != 0:
            return None
        extra: dict[str, str] = {}
        for line in proc.stdout.splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            if key.strip() == "License" and value.strip():
                extra["license"] = value.strip()
        return extra or None
