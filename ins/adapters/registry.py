"""Adapter discovery and source detection."""

from __future__ import annotations

import os

from ins.adapters.apk_adapter import ApkAdapter
from ins.adapters.apt_adapter import AptAdapter
from ins.adapters.base import SourceAdapter
from ins.adapters.dnf_adapter import DnfAdapter
from ins.adapters.flatpak_adapter import FlatpakAdapter
from ins.adapters.nix_adapter import NixAdapter
from ins.adapters.pacman_adapter import PacmanAdapter
from ins.adapters.snap_adapter import SnapAdapter
from ins.adapters.zypper_adapter import ZypperAdapter

REGISTERED = (
    AptAdapter,
    FlatpakAdapter,
    DnfAdapter,
    PacmanAdapter,
    ZypperAdapter,
    SnapAdapter,
    NixAdapter,
    ApkAdapter,
)


def _instances() -> list[SourceAdapter]:
    out: list[SourceAdapter] = []
    if os.environ.get("INS_FAKE"):
        from ins.adapters.fake_adapter import FakeAdapter

        out.append(FakeAdapter("fake"))
        out.append(FakeAdapter("fake2"))
    out.extend(cls() for cls in REGISTERED)
    return out


def known_sources() -> list[str]:
    """All source names the tool can speak, available or not."""
    names = [cls.name for cls in REGISTERED]
    if os.environ.get("INS_FAKE"):
        names = ["fake", "fake2", *names]
    return names


def detect_sources(config) -> list[SourceAdapter]:
    """Instances that are usable on this system, in config priority order."""
    available = [a for a in _instances() if a.is_available()]
    ordered: list[SourceAdapter] = []
    for name in config.source_priority:
        for adapter in available:
            if adapter.name == name and adapter not in ordered:
                ordered.append(adapter)
    for adapter in available:
        if adapter not in ordered:
            ordered.append(adapter)
    return ordered


def get_source(name: str, config) -> SourceAdapter | None:
    for adapter in detect_sources(config):
        if adapter.name == name:
            return adapter
    return None
