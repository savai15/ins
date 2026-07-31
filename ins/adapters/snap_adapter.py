"""Snap adapter (Ubuntu snapd)."""

from __future__ import annotations

import re
import shutil

from ins.adapters._subprocess import run, run_privileged, run_privileged_stream
from ins.adapters.base import SourceAdapter
from ins.models import AppInfo

_SEARCH_TIMEOUT = 60.0


def _split_columns(line: str) -> list[str]:
    """Split a snap table row on column padding; fall back to plain split."""
    parts = re.split(r"\s{2,}", line.strip())
    if len(parts) >= 2:
        return parts
    return line.split()


class SnapAdapter(SourceAdapter):
    name = "snap"
    priority = 55

    def is_available(self) -> bool:
        return shutil.which("snap") is not None

    # ---------------------------------------------------------------- search

    def search(self, query: str, limit: int = 25) -> list[AppInfo]:
        proc = run(
            ["snap", "find", "--color=never", query],
            timeout=_SEARCH_TIMEOUT,
            check=False,
        )
        if proc.returncode != 0 or "No matching snaps" in proc.stdout:
            return []
        out: list[AppInfo] = []
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            stripped = line.lstrip()
            if stripped.startswith("Name") or stripped.startswith("---"):
                continue
            cols = _split_columns(line)
            if len(cols) < 2:
                continue
            summary = " ".join(cols[4:]) if len(cols) > 4 else ""
            out.append(
                AppInfo(
                    id=cols[0],
                    name=cols[0],
                    description=summary,
                    source=self.name,
                    version=cols[1],
                )
            )
            if len(out) >= limit:
                break
        return out

    # ---------------------------------------------------------- list_installed

    def list_installed(self) -> list[AppInfo]:
        proc = run(["snap", "list"], timeout=_SEARCH_TIMEOUT)
        out: list[AppInfo] = []
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            if line.lstrip().startswith("Name"):
                continue
            cols = _split_columns(line)
            if len(cols) < 2:
                continue
            out.append(
                AppInfo(
                    id=cols[0],
                    name=cols[0],
                    source=self.name,
                    version=cols[1],
                    installed=True,
                )
            )
        return out

    # --------------------------------------------------------- install/remove

    def install(self, package_id: str, on_progress=None) -> bool:
        cmd = ["snap", "install", package_id]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return True

    def remove(self, package_id: str, on_progress=None) -> bool:
        cmd = ["snap", "remove", package_id]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return True

    # ----------------------------------------------------------------- update

    def update(self, on_progress=None) -> int:
        cmd = ["snap", "refresh"]
        lines: list[str] = []
        if on_progress is not None:
            def collect(line: str) -> None:
                lines.append(line)
                on_progress(line)

            run_privileged_stream(cmd, collect, timeout=600)
        else:
            proc = run_privileged(cmd, timeout=600)
            lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        return sum(1 for ln in lines if "All snaps up to date" not in ln)

    # ------------------------------------------------------------------- info

    def info(self, package_id: str) -> dict[str, str] | None:
        proc = run(["snap", "info", package_id], timeout=_SEARCH_TIMEOUT, check=False)
        if proc.returncode != 0:
            return None
        extra: dict[str, str] = {}
        for line in proc.stdout.splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key == "license" and value and value != "unset":
                extra["license"] = value
            elif key == "description" and value:
                extra["description"] = value
        return extra or None
