"""Flatpak adapter (user-space installs, no root required)."""

from __future__ import annotations

import shutil

from ins.adapters._subprocess import AdapterError, check_rc, run, run_stream
from ins.adapters.base import SourceAdapter
from ins.models import AppInfo

_SEARCH_TIMEOUT = 60.0


class FlatpakAdapter(SourceAdapter):
    name = "flatpak"
    priority = 20

    def is_available(self) -> bool:
        return shutil.which("flatpak") is not None

    # ---------------------------------------------------------------- search

    def search(self, query: str, limit: int = 25) -> list[AppInfo]:
        proc = run(
            ["flatpak", "search", "--columns=application,version,branch,remotes,description", query],
            timeout=_SEARCH_TIMEOUT,
            check=False,
        )
        if proc.returncode == 1 and "No matches found" in proc.stderr:
            return []
        check_rc(proc, ["flatpak", "search", query], allowed=(0, 1))
        installed = self._installed_ids()
        out: list[AppInfo] = []
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            cols = line.split("\t")
            app_id = cols[0].strip()
            if not app_id or app_id in ("Application", "Name"):
                continue
            version = cols[1].strip() if len(cols) > 1 else ""
            remotes = cols[3].strip() if len(cols) > 3 else ""
            description = cols[4].strip() if len(cols) > 4 else ""
            if len(cols) > 5:
                description = "\t".join(cols[4:]).strip()
            out.append(
                AppInfo(
                    id=app_id,
                    name=_human_name(app_id),
                    description=description,
                    source=self.name,
                    version=version,
                    installed=app_id in installed,
                )
            )
            if len(out) >= limit:
                break
        return out

    def _installed_ids(self) -> set[str]:
        ids: set[str] = set()
        for scope in ("--user", "--system"):
            proc = run(
                ["flatpak", "list", scope, "--app", "--columns=application"],
                timeout=_SEARCH_TIMEOUT,
                check=False,
            )
            if proc.returncode != 0:
                continue
            for line in proc.stdout.splitlines():
                app_id = line.strip().split("\t", 1)[0].strip()
                if app_id:
                    ids.add(app_id)
        return ids

    # ---------------------------------------------------------- list_installed

    def list_installed(self) -> list[AppInfo]:
        seen: set[str] = set()
        out: list[AppInfo] = []
        for scope in ("--user", "--system"):
            proc = run(
                ["flatpak", "list", scope, "--app", "--columns=application,version,branch,description"],
                timeout=_SEARCH_TIMEOUT,
                check=False,
            )
            if proc.returncode != 0:
                continue
            for line in proc.stdout.splitlines():
                cols = [c.strip() for c in line.split("\t")]
                if not cols or not cols[0]:
                    continue
                app_id = cols[0]
                if app_id in seen:
                    continue
                seen.add(app_id)
                out.append(
                    AppInfo(
                        id=app_id,
                        name=_human_name(app_id),
                        description=cols[3] if len(cols) > 3 else "",
                        source=self.name,
                        version=cols[1] if len(cols) > 1 else "",
                        installed=True,
                    )
                )
        return out

    # --------------------------------------------------------- install/remove

    def install(self, package_id: str, on_progress=None) -> bool:
        remote = self._find_remote(package_id)
        cmd = ["flatpak", "install", "--user", "--noninteractive", "-y"]
        if remote:
            cmd.append(remote)
        cmd.append(package_id)
        if on_progress is not None:
            run_stream(cmd, on_progress, timeout=600)
        else:
            run(cmd, timeout=600)
        return True

    def _find_remote(self, package_id: str) -> str | None:
        try:
            proc = run(
                ["flatpak", "search", "--columns=application,remotes", package_id],
                timeout=_SEARCH_TIMEOUT,
                check=False,
            )
        except AdapterError:
            return None
        if proc.returncode != 0:
            return None
        for line in proc.stdout.splitlines():
            cols = line.split("\t")
            if len(cols) < 2:
                continue
            if cols[0].strip() != package_id:
                continue
            remotes = cols[1].strip()
            return remotes.split(",")[0].strip() if remotes else None
        return None

    def remove(self, package_id: str, on_progress=None) -> bool:
        cmd = ["flatpak", "uninstall", "--user", "-y", package_id]
        if on_progress is not None:
            run_stream(cmd, on_progress, timeout=600)
        else:
            run(cmd, timeout=600)
        return True

    # ----------------------------------------------------------------- update

    def update(self, on_progress=None) -> int:
        cmd = ["flatpak", "update", "--user", "--noninteractive", "-y"]
        lines: list[str] = []
        if on_progress is not None:
            def collect(line: str) -> None:
                lines.append(line)
                on_progress(line)

            run_stream(cmd, collect, timeout=600)
        else:
            proc = run(cmd, timeout=600)
            lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        return sum(1 for ln in lines if ln.startswith("Updated "))

    # ---------------------------------------------------------- outdated/upgrade

    def outdated(self) -> list[AppInfo]:
        proc = run(
            ["flatpak", "remote-ls", "--updates", "--columns=application,version"],
            timeout=_SEARCH_TIMEOUT,
            check=False,
        )
        if proc.returncode != 0:
            return []
        out: list[AppInfo] = []
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            cols = line.split("\t")
            app = cols[0].strip()
            if not app:
                continue
            out.append(
                AppInfo(
                    id=app,
                    name=_human_name(app),
                    source=self.name,
                    version="",
                    available=cols[1].strip() if len(cols) > 1 else "",
                    installed=True,
                )
            )
        return out

    def upgrade(self, package_id: str, on_progress=None) -> bool:
        cmd = ["flatpak", "update", "--user", "-y", package_id]
        if on_progress is not None:
            run_stream(cmd, on_progress, timeout=600)
        else:
            run(cmd, timeout=600)
        return True

    # ------------------------------------------------------------------- info

    def info(self, package_id: str) -> dict[str, str] | None:
        proc = run(["flatpak", "info", package_id], timeout=_SEARCH_TIMEOUT, check=False)
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


def _human_name(app_id: str) -> str:
    """org.videolan.VLC -> VLC"""
    return app_id.split(".")[-1]
