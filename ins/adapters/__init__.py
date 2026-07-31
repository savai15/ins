"""Package source adapters (apt, flatpak, dnf, pacman, zypper, nix, apk)."""

from ins.adapters.base import SourceAdapter
from ins.adapters.registry import detect_sources, get_source, known_sources

__all__ = [
    "SourceAdapter",
    "detect_sources",
    "get_source",
    "known_sources",
]
