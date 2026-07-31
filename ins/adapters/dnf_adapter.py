"""DNF adapter (Fedora/RHEL/CentOS)."""

from __future__ import annotations

import re
import shutil

from ins.adapters._subprocess import check_rc, run, run_privileged, run_privileged_stream
from ins.adapters.base import SourceAdapter
from ins.models import AppInfo

_SEARCH_TIMEOUT = 60.0

_ARCH_SUFFIX_RE = re.compile(r"\.(x86_64|i686|noarch|aarch64|armv7hl|ppc64le|s390x)$")


class DnfAdapter(SourceAdapter):
    name = "dnf"
    priority = 30

    def is_available(self) -> bool:
        return shutil.which("dnf") is not None and shutil.which("rpm") is not None

    def search(self, query: str, limit: int = 25) -> list[AppInfo]:
        proc = run(["dnf", "search", "-q", query], timeout=_SEARCH_TIMEOUT, check=False)
        if proc.returncode == 1:
            combined = (proc.stdout + proc.stderr).strip()
            if not combined or "No matches found" in combined:
                return []
        check_rc(proc, ["dnf", "search", query], allowed=(0, 1))
        out: list[AppInfo] = []
        for line in proc.stdout.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("="):
                continue
            if ": " not in stripped:
                continue
            name, _, summary = stripped.partition(": ")
            name = name.strip()
            if not name or not summary:
                continue
            if name.startswith("Last metadata") or name.startswith("Name"):
                continue
            out.append(
                AppInfo(
                    id=name,
                    name=name,
                    description=summary,
                    source=self.name,
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
        cmd = ["dnf", "install", "-y", package_id]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return True

    def remove(self, package_id: str, on_progress=None) -> bool:
        cmd = ["dnf", "remove", "-y", package_id]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return True

    # ----------------------------------------------------------------- update

    def update(self, on_progress=None) -> int:
        cmd = ["dnf", "upgrade", "-y"]
        lines: list[str] = []
        if on_progress is not None:
            def collect(line: str) -> None:
                lines.append(line)
                on_progress(line)

            run_privileged_stream(cmd, collect, timeout=600)
        else:
            proc = run_privileged(cmd, timeout=600)
            lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        if any(ln == "Nothing to do." for ln in lines):
            return 0
        after_upgraded = False
        count = 0
        for line in lines:
            if line == "Upgraded:":
                after_upgraded = True
                continue
            if after_upgraded:
                if not line.startswith(" "):
                    break
                count += 1
        return count

    # ---------------------------------------------------------- outdated/upgrade

    def outdated(self) -> list[AppInfo]:
        proc = run(["dnf", "list", "--upgrades", "-q"], timeout=_SEARCH_TIMEOUT, check=False)
        out: list[AppInfo] = []
        for line in proc.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            name = _ARCH_SUFFIX_RE.sub("", parts[0])
            out.append(
                AppInfo(
                    id=name,
                    name=name,
                    source=self.name,
                    version="",
                    available=parts[1],
                    installed=True,
                )
            )
        return out

    def upgrade(self, package_id: str, on_progress=None) -> bool:
        cmd = ["dnf", "upgrade", "-y", package_id]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return True

    # ------------------------------------------------------------------- info

    def info(self, package_id: str) -> dict[str, str] | None:
        proc = run(["dnf", "info", package_id], timeout=_SEARCH_TIMEOUT, check=False)
        if proc.returncode != 0:
            return None
        extra: dict[str, str] = {}
        for line in proc.stdout.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            if key in ("License", "URL", "Description") and value:
                extra[key.lower()] = value
            elif "description" in extra and line[:1].isspace():
                extra["description"] += " " + stripped
        if "url" in extra:
            extra["homepage"] = extra.pop("url")
        return extra or None
