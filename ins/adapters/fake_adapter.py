"""Demo adapter for exercising ins end-to-end without a real package manager.

Only registered when INS_FAKE=1 is set in the environment; it is never active
on a real system unless explicitly requested for a demo.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from rapidfuzz import fuzz

from ins.adapters.base import SourceAdapter
from ins.models import AppInfo

CATALOG = [
    AppInfo(id="vlc", name="vlc", description="VLC media player - the portable version", version="3.0.20", size=25432064, popularity=0.95),
    AppInfo(id="firefox", name="firefox", description="Standalone web browser from mozilla.org", version="130.0", size=201326592, popularity=0.98),
    AppInfo(id="gimp", name="gimp", description="GNU Image Manipulation Program", version="2.10.38", size=167772160, popularity=0.80),
    AppInfo(id="git", name="git", description="fast, scalable, distributed revision control system", version="2.45.2", size=41943040, popularity=0.70),
    AppInfo(id="neovim", name="neovim", description="hyperextensible Vim-based text editor", version="0.10.0", size=18874368, popularity=0.75),
    AppInfo(id="htop", name="htop", description="interactive process viewer", version="3.3.0", size=1048576, popularity=0.60),
    AppInfo(id="tmux", name="tmux", description="terminal multiplexer", version="3.4", size=2097152, popularity=0.55),
    AppInfo(id="curl", name="curl", description="command line tool for transferring data with URL syntax", version="8.9.1", size=3145728, popularity=0.50),
    AppInfo(id="python3", name="python3", description="interactive high-level object-oriented language", version="3.12.4", size=8388608, popularity=0.65),
]

_STATE: dict[str, set[str]] = {}


def _state_file(name: str) -> Path:
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home) if data_home else Path.home() / ".local" / "share"
    return base / "ins" / f"fake_{name}.json"


class FakeAdapter(SourceAdapter):
    def __init__(self, name: str = "fake"):
        self.name = name
        self.priority = 5 if name == "fake" else 6
        self._file = _state_file(name)
        _STATE.setdefault(self.name, set())
        if self._file.is_file():
            try:
                _STATE[self.name] = set(json.loads(self._file.read_text(encoding="utf-8-sig")))
            except (ValueError, OSError):
                _STATE[self.name] = set()

    def _save(self) -> None:
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            self._file.write_text(json.dumps(sorted(_STATE[self.name])), encoding="utf-8")
        except OSError:
            pass

    def is_available(self) -> bool:
        return True

    def _catalog(self) -> list[AppInfo]:
        installed_ids = _STATE[self.name]
        out: list[AppInfo] = []
        for info in CATALOG:
            out.append(
                AppInfo(
                    id=info.id,
                    name=info.name,
                    description=info.description,
                    source=self.name,
                    version=info.version,
                    size=info.size,
                    installed=info.id in installed_ids,
                    popularity=info.popularity,
                )
            )
        return out

    def search(self, query: str, limit: int = 25) -> list[AppInfo]:
        q = query.lower()
        hits = []
        for info in self._catalog():
            if q in info.name.lower() or q in info.description.lower():
                hits.append(info)
        if not hits:
            for info in self._catalog():
                if fuzz.ratio(q, info.name.lower()) >= 60 or fuzz.partial_ratio(q, info.description.lower()) >= 80:
                    hits.append(info)
        return hits[:limit]

    def list_installed(self) -> list[AppInfo]:
        return [info for info in self._catalog() if info.installed]

    def install(self, package_id: str, on_progress=None) -> bool:
        if any(info.id == package_id for info in CATALOG):
            _STATE[self.name].add(package_id)
            self._save()
            if on_progress is not None:
                on_progress(f"Installing: {package_id}")
                on_progress("Done.")
            return True
        return False

    def remove(self, package_id: str, on_progress=None) -> bool:
        if package_id in _STATE[self.name]:
            _STATE[self.name].discard(package_id)
            self._save()
            if on_progress is not None:
                on_progress(f"Removing: {package_id}")
                on_progress("Done.")
            return True
        return False

    def update(self, on_progress=None) -> int:
        if on_progress is not None:
            on_progress("Checking for updates…")
            on_progress("3 updates available")
            on_progress("Updating vlc…")
            on_progress("Updating firefox…")
            on_progress("Done.")
        return 3

    def info(self, package_id: str) -> dict[str, str] | None:
        for info in CATALOG:
            if info.id == package_id:
                return {
                    "license": "GPL-2.0",
                    "homepage": f"https://example.org/apps/{package_id}",
                    "description": info.description,
                }
        return None
