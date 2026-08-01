"""APT adapter (Debian/Ubuntu).

Uses python-apt when importable; falls back to apt-cache/dpkg-query/apt-get
subprocesses otherwise so the adapter works on any dpkg-based system.
"""

from __future__ import annotations

import os
import shutil

from ins.adapters._subprocess import AdapterError, run, run_privileged, run_privileged_stream
from ins.adapters.base import SourceAdapter
from ins.models import AppInfo

_SEARCH_TIMEOUT = 60.0


def _typo_score(query: str, name: str, score_cutoff: float | None = None) -> float:
    """Typo-tolerant name match: order similarity (partial_ratio) plus how
    much of the query's letter set the name covers. `vcl` -> `vlc` scores
    high (same letters, wrong order); long unrelated names like
    `webdavclient` score low even though they contain the letters."""
    from collections import Counter

    from rapidfuzz import fuzz

    q = Counter(query.lower())
    n = Counter(name.lower())
    overlap = sum((q & n).values())
    # How much of BOTH strings the shared letters cover: a long junk query
    # (e.g. 'zzzzqqqq') shares few letters with a short real name, so its
    # density stays low even though partial_ratio can be high.
    density = min(
        overlap / len(query) if query else 0.0,
        overlap / len(name) if name else 0.0,
    )
    score = 0.6 * fuzz.partial_ratio(query, name) + 0.4 * 100.0 * density
    if score_cutoff is not None and score < score_cutoff:
        return 0
    return score


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
                return self._fuzzy_name_fallback(query, results, limit)
        results = self._search_subprocess(query, limit)
        return self._fuzzy_name_fallback(query, results, limit)

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
        query_l = query.lower()
        seen: set[str] = set()
        out: list[AppInfo] = []
        # python-apt >= 3.0 has no Cache.search(); match names by substring.
        for pkg in cache:
            name = pkg.name
            if query_l not in name.lower():
                continue
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
            for pkg in cache:
                name = pkg.name
                if name in seen:
                    continue
                cand = pkg.candidate
                if cand is None:
                    continue
                desc = (cand.description or "").split("\n")[0].strip()
                if query_l not in desc.lower():
                    continue
                seen.add(name)
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
        # apt-cache prints "name - short description" (or bare names on some
        # distros); only the name may be passed to `apt-cache show`.
        names = [
            ln.split(" - ", 1)[0].strip() for ln in proc.stdout.splitlines() if ln.strip()
        ]
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
            desc = _apt_description(block)
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

    # --------------------------------------------------- fuzzy name fallback

    def _fuzzy_name_fallback(self, query: str, results: list[AppInfo], limit: int) -> list[AppInfo]:
        """apt-cache only matches names/descriptions literally, so a typo like
        `vcl` misses `vlc`. When nothing returned is a (near-)exact name
        match, fuzzy match against the full package-name list
        (`apt-cache pkgnames`, a fast local call) and surface the best hits
        first — name matches beat description matches."""
        from rapidfuzz import fuzz, process

        q_l = query.lower()
        if any(r.name.lower() == q_l or fuzz.ratio(query, r.name) >= 90 for r in results):
            return results
        try:
            names = run(["apt-cache", "pkgnames"], timeout=_SEARCH_TIMEOUT).stdout.splitlines()
        except AdapterError:
            return results
        names = [n.strip() for n in names if n.strip()]
        if not names:
            return results
        matches = [
            (name, score)
            for name, score, _ in process.extract(query, names, scorer=_typo_score, limit=8)
            if score >= 70
        ]
        if not matches:
            return results
        try:
            show = run(["apt-cache", "show", *[n for n, _ in matches]], timeout=_SEARCH_TIMEOUT)
        except AdapterError:
            return results
        shown: list[AppInfo] = []
        for block in _parse_apt_show(show.stdout):
            name = block.get("Package", "")
            if not name:
                continue
            try:
                size = int(block.get("Installed-Size", "0")) * 1024
            except ValueError:
                size = 0
            shown.append(
                AppInfo(
                    id=name,
                    name=name,
                    description=_apt_description(block),
                    source=self.name,
                    version=block.get("Version", ""),
                    size=size,
                    installed="installed" in block.get("Status", ""),
                )
            )
        if not shown:
            return results
        seen = {r.id for r in results}
        return (shown + [r for r in results if r.id not in seen])[:limit]

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

    # ---------------------------------------------------------- outdated/upgrade

    def outdated(self) -> list[AppInfo]:
        proc = run(["apt", "list", "--upgradable"], timeout=_SEARCH_TIMEOUT, check=False)
        out: list[AppInfo] = []
        marker = "upgradable to: "
        for line in proc.stdout.splitlines():
            if marker not in line:
                continue
            name = line.split("/", 1)[0].strip()
            installed = line.split()[1]
            available = line.split(marker, 1)[1].split("]", 1)[0].strip()
            if not name:
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
        cmd = ["apt-get", "-y", "install", "--only-upgrade", package_id]
        if on_progress is not None:
            run_privileged_stream(cmd, on_progress, timeout=600)
        else:
            run_privileged(cmd, timeout=600)
        return True

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
            desc = block.get("Description") or next(
                (v for k, v in block.items() if k.startswith("Description")), ""
            )
            description = desc.strip()
            if description:
                extra["description"] = description
            return extra or None
        return None


def _apt_description(block: dict[str, str]) -> str:
    """Short description from an `apt-cache show` block; Ubuntu localizes
    the field as `Description-en`, Debian uses plain `Description`."""
    desc = block.get("Description") or next(
        (v for k, v in block.items() if k.startswith("Description")), ""
    )
    return desc.split("\n")[0].strip()


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
                joiner = "\n" if last_key.startswith("Description") else " "
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
