"""Declarative machine provisioning: `ins export` and `ins bundle`.

A manifest is a TOML file mapping source -> package id -> version:

    [packages.apt]
    vlc = "3.0.20-0+deb12u1"

    [packages.flatpak]
    org.mozilla.firefox = "130.0"

`ins export` writes one from the current machine; `ins bundle check` reports
drift against it; `ins bundle install` installs what's missing.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import tomli_w


def build_manifest(installed: list) -> dict[str, dict[str, dict[str, str]]]:
    """Group installed apps by source: {source: {id: version}}."""
    packages: dict[str, dict[str, str]] = {}
    for info in installed:
        packages.setdefault(info.source, {})[info.id] = info.version or ""
    return {"packages": packages}


def dumps(installed: list) -> str:
    """Render a manifest for `installed` apps as TOML text."""
    return tomli_w.dumps(build_manifest(installed))


def load_manifest(path: str | Path) -> dict[str, dict[str, str]]:
    """Read a manifest file; raises ValueError on malformed content."""
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    packages = data.get("packages")
    if not isinstance(packages, dict):
        raise ValueError("missing [packages] section")
    return {
        str(source): {str(pkg): str(version or "") for pkg, version in items.items()}
        for source, items in packages.items()
        if isinstance(items, dict)
    }


def check(
    manifest: dict[str, dict[str, str]],
    installed: list,
) -> dict[str, Any]:
    """Diff a manifest against what's actually installed.

    Returns {"missing": [(source, pkg), ...],
             "mismatched": [(source, pkg, installed, required), ...],
             "extra": [(source, pkg), ...]}.
    """
    installed_by_source: dict[str, dict[str, str]] = {}
    for info in installed:
        installed_by_source.setdefault(info.source, {})[info.id] = info.version or ""

    missing: list[tuple[str, str]] = []
    mismatched: list[tuple[str, str, str, str]] = []
    for source, items in manifest.items():
        have = installed_by_source.get(source, {})
        for pkg_id, want_version in items.items():
            got = have.get(pkg_id)
            if got is None:
                missing.append((source, pkg_id))
            elif want_version and got and want_version != got:
                mismatched.append((source, pkg_id, got, want_version))

    extra: list[tuple[str, str]] = [
        (source, pkg_id)
        for source, items in installed_by_source.items()
        for pkg_id in items
        if pkg_id not in manifest.get(source, {})
    ]
    return {"missing": missing, "mismatched": mismatched, "extra": extra}
