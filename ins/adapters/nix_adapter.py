"""Nix adapter (Nix/NixOS, user-level installs via nix-env)."""

from __future__ import annotations

import shutil

from ins.adapters._subprocess import CommandFailed, run, run_stream, split_name_version
from ins.adapters.base import SourceAdapter
from ins.models import AppInfo

_SEARCH_TIMEOUT = 90.0


class NixAdapter(SourceAdapter):
    name = "nix"
    priority = 60

    def is_available(self) -> bool:
        return shutil.which("nix") is not None and shutil.which("nix-env") is not None

    def search(self, query: str, limit: int = 25) -> list[AppInfo]:
        proc = run(["nix", "search", "nixpkgs", query], timeout=_SEARCH_TIMEOUT)
        installed = self._installed_names()
        lines = proc.stdout.splitlines()
        out: list[AppInfo] = []
        i = 0
        while i < len(lines) and len(out) < limit:
            line = lines[i]
            if not line.startswith("* "):
                i += 1
                continue
            rest = line[2:].strip()
            attr, _, ver = rest.partition(" (")
            version = ver.rstrip(")").strip() if ver else ""
            name = attr.split(".")[-1]
            description = ""
            if i + 1 < len(lines) and lines[i + 1][:1] == " " and not lines[i + 1].startswith("*"):
                description = lines[i + 1].strip()
            out.append(
                AppInfo(
                    id=attr,
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
            proc = run(["nix-env", "-q"], timeout=_SEARCH_TIMEOUT)
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
        proc = run(["nix-env", "-q"], timeout=_SEARCH_TIMEOUT)
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
        name = package_id.split(".")[-1]
        attr = package_id if package_id.startswith("nixpkgs.") else f"nixpkgs.{name}"
        cmd = ["nix-env", "-iA", attr]
        if on_progress is not None:
            run_stream(cmd, on_progress, timeout=900)
        else:
            run(cmd, timeout=900)
        return True

    def remove(self, package_id: str, on_progress=None) -> bool:
        cmd = ["nix-env", "-e", package_id]
        if on_progress is not None:
            run_stream(cmd, on_progress, timeout=600)
        else:
            run(cmd, timeout=600)
        return True

    # ---------------------------------------------------------- outdated/upgrade

    # nix-env tracks versions per user profile; upgrades are resolved at run
    # time by nix itself, so no dedicated outdated query is exposed.

    def upgrade(self, package_id: str, on_progress=None) -> bool:
        cmd = ["nix-env", "-u", package_id]
        if on_progress is not None:
            run_stream(cmd, on_progress, timeout=900)
        else:
            run(cmd, timeout=900)
        return True

    # ----------------------------------------------------------------- update

    def update(self, on_progress=None) -> int:
        cmd = ["nix-channel", "--update"]
        if on_progress is not None:
            run_stream(cmd, on_progress, timeout=900)
        else:
            run(cmd, timeout=900)
        return 0
