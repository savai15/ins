"""APK adapter (Alpine Linux)."""

from __future__ import annotations

import re
import shutil

from ins.adapters._subprocess import CommandFailed, run, run_privileged, run_privileged_stream, split_name_version
from ins.adapters.base import SourceAdapter
from ins.models import AppInfo

_SEARCH_TIMEOUT = 60.0

_UPGRADING_RE = re.compile(r"Upgrading (\S+) \(.*? -> (\S+)\)")


class ApkAdapter(SourceAdapter):
    name = "apk"
    priority = 70

    def is_available(self) -> bool:
        return shutil.which("apk") is not None

    def search(self, query: str, limit: int = 25) -> list[AppInfo]:
        proc = run(["apk", "search", "-d", query], timeout=_SEARCH_TIMEOUT)
        installed = self._installed_names()
        out: list[AppInfo] = []
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            name, _, desc = line.partition(" - ")
            name = name.strip()
            if not name:
                continue
            out.append(
                AppInfo(
                    id=name,
                    name=name,
                    description=desc.strip(),
                    source=self.name,
                    installed=name in installed,
                )
            )
            if len(out) >= limit:
                break
        return out

    def _installed_names(self) -> set[str]:
        try:
            proc = run(["apk", "info", "-v"], timeout=_SEARCH_TIMEOUT)
        except CommandFailed:
            return set()
        names: set[str] = set()
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            name, _ = split_name_version(line)
            if name:
                names.add(name)
        return names

    def list_installed(self) -> list[AppInfo]:
        proc = run(["apk", "info", "-v"], timeout=_SEARCH_TIMEOUT)
        out: list[AppInfo] = []
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            name, version = split_name_version(line)
            out.append(
                AppInfo(
                    id=name,
                    name=name,
                    source=self.name,
                    version=version,
                    installed=True,
                )
            )
        return out

    def install(self, package_id: str, on_progress=None) -> bool:
        cmd = ["apk", "add", package_id]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return True

    def remove(self, package_id: str, on_progress=None) -> bool:
        cmd = ["apk", "del", package_id]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return True

    # ---------------------------------------------------------- outdated/upgrade

    def outdated(self) -> list[AppInfo]:
        proc = run(["apk", "upgrade", "-s"], timeout=_SEARCH_TIMEOUT, check=False)
        out: list[AppInfo] = []
        for line in proc.stdout.splitlines():
            match = _UPGRADING_RE.search(line)
            if not match:
                continue
            out.append(
                AppInfo(
                    id=match.group(1),
                    name=match.group(1),
                    source=self.name,
                    version="",
                    available=match.group(2),
                    installed=True,
                )
            )
        return out

    def upgrade(self, package_id: str, on_progress=None) -> bool:
        cmd = ["apk", "add", "-u", package_id]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return True

    # ----------------------------------------------------------------- update

    def update(self, on_progress=None) -> int:
        cmd = ["apk", "update"]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return 0
