"""APT adapter (Debian/Ubuntu).

Uses python-apt when importable; falls back to apt-cache/dpkg-query/apt-get
subprocesses otherwise so the adapter works on any dpkg-based system.
"""

from __future__ import annotations

import os
import shutil

from ins.adapters._subprocess import run, run_privileged, run_privileged_stream
from ins.adapters.base import SourceAdapter
from ins.models import AppInfo

_SEARCH_TIMEOUT = 60.0


class AptAdapter(SourceAdapter):
    name = "apt"
    priority = 10

    def is_available(self) -> bool:
        return shutil.which("apt-get") is not None and os.path.exists("/var/lib/dpkg/status")

    # ---------------------------------------------------------------- search

    def search(self, query: str, limit: int = 25) -> list[AppInfo]:
        if self._has_python_apt():
            try:
                results = self._search_python_apt(query, limit)
            except Exception:
                results = None
            if results is not None:
                return results
        return self._search_subprocess(query, limit)

    @staticmethod
    def _has_python_apt() -> bool:
        try:
            import apt  # noqa: F401
        except ImportError:
            return False
        return True

    def _search_python_apt(self, query: str, limit: int) -> list[AppInfo] | None:
        import apt

        cache = apt.Cache()
        seen: set[str] = set()
        out: list[AppInfo] = []
        for pkg in cache.search(query):
            name = pkg.name
            if name in seen:
                continue
            seen.add(name)
            cand = pkg.candidate
            if cand is None:
                continue
            desc = (cand.description or "").split("\n")[0].strip()
            out.append(
                AppInfo(
                    id=name,
                    name=name,
                    description=desc,
                    source=self.name,
                    version=cand.version,
                    size=int(cand.size),
                    installed=pkg.is_installed,
                )
            )
            if len(out) >= limit:
                return out
        if len(out) < limit:
            for pkg in cache.search(query, search_descriptions=True):
                name = pkg.name
                if name in seen:
                    continue
                seen.add(name)
                cand = pkg.candidate
                if cand is None:
                    continue
                desc = (cand.description or "").split("\n")[0].strip()
                out.append(
                    AppInfo(
                        id=name,
                        name=name,
                        description=desc,
                        source=self.name,
                        version=cand.version,
                        size=int(cand.size),
                        installed=pkg.is_installed,
                    )
                )
                if len(out) >= limit:
                    break
        return out

    def _search_subprocess(self, query: str, limit: int) -> list[AppInfo]:
        proc = run(["apt-cache", "search", "--names-only", query], timeout=_SEARCH_TIMEOUT)
        names = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        if not names:
            return []
        names = names[:limit]
        show = run(["apt-cache", "show", *names], timeout=_SEARCH_TIMEOUT)
        blocks = _parse_apt_show(show.stdout)
        out: list[AppInfo] = []
        for block in blocks:
            name = block.get("Package", "")
            if not name:
                continue
            version = block.get("Version", "")
            installed = "installed" in block.get("Status", "")
            size_kb = block.get("Installed-Size", "0")
            try:
                size = int(size_kb) * 1024
            except ValueError:
                size = 0
            desc = block.get("Description", "").split("\n")[0].strip()
            out.append(
                AppInfo(
                    id=name,
                    name=name,
                    description=desc,
                    source=self.name,
                    version=version,
                    size=size,
                    installed=installed,
                )
            )
        return out

    # ---------------------------------------------------------- list_installed

    def list_installed(self) -> list[AppInfo]:
        if self._has_python_apt():
            try:
                return self._list_installed_python_apt()
            except Exception:
                pass
        return self._list_installed_subprocess()

    def _list_installed_python_apt(self) -> list[AppInfo]:
        import apt

        cache = apt.Cache()
        out: list[AppInfo] = []
        for pkg in cache:
            if not pkg.is_installed:
                continue
            inst = pkg.installed
            desc = (inst.description or "").split("\n")[0].strip()
            out.append(
                AppInfo(
                    id=pkg.name,
                    name=pkg.name,
                    description=desc,
                    source=self.name,
                    version=inst.version,
                    installed=True,
                )
            )
        return out

    def _list_installed_subprocess(self) -> list[AppInfo]:
        proc = run(
            ["dpkg-query", "-W", "-f=${Package}\t${Version}\n"],
            timeout=_SEARCH_TIMEOUT,
        )
        out: list[AppInfo] = []
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            name, version = parts[0], parts[1]
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

    # --------------------------------------------------------- install/remove

    def install(self, package_id: str, on_progress=None) -> bool:
        cmd = ["apt-get", "-y", "install", package_id]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return True

    def remove(self, package_id: str, on_progress=None) -> bool:
        cmd = ["apt-get", "-y", "remove", package_id]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return True

    # ----------------------------------------------------------------- update

    def update(self, on_progress=None) -> int:
        import re as _re

        cmd = ["apt-get", "update"]
        lines: list[str] = []
        if on_progress is not None:
            def collect(line: str) -> None:
                lines.append(line)
                on_progress(line)

            run_privileged_stream(cmd, collect, timeout=600)
        else:
            proc = run_privileged(cmd, timeout=600)
            lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        for line in lines:
            match = _re.search(r"(\d+)\s+package[s]?\s+can be upgraded", line)
            if match:
                return int(match.group(1))
        return 0

    # ------------------------------------------------------------------- info

    def info(self, package_id: str) -> dict[str, str] | None:
        proc = run(
            ["apt-cache", "show", package_id],
            timeout=_SEARCH_TIMEOUT,
            check=False,
        )
        if proc.returncode != 0:
            return None
        for block in _parse_apt_show(proc.stdout):
            if block.get("Package", "") != package_id:
                continue
            extra: dict[str, str] = {}
            homepage = block.get("Homepage", "")
            if homepage:
                extra["homepage"] = homepage
            description = block.get("Description", "")
            if description:
                extra["description"] = description
            return extra or None
        return None


def _parse_apt_show(text: str) -> list[dict[str, str]]:
    """Parse `apt-cache show` output into field blocks (continuation-aware).

    Description continuation lines keep their newlines so the short summary
    (first line) can be split from the long description.
    """
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    last_key = ""
    for line in text.splitlines():
        if not line.strip():
            current = None
            last_key = ""
            continue
        if line[:1] in (" ", "\t"):
            if current is not None and last_key:
                joiner = "\n" if last_key == "Description" else " "
                current[last_key] = current[last_key] + joiner + line.strip()
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            if not key:
                continue
            if current is None:
                current = {}
                blocks.append(current)
            current[key] = value.strip()
            last_key = key
    return blocks
