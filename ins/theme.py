"""Pastel color constants for source tags and status messages.

Colors are raw hex strings so they work with `rich` out of the box.
"""

from __future__ import annotations

# Source tag colors
DUSTY_PEACH = "#E8A87C"  # apt, dnf, pacman, zypper
SOFT_BLUE = "#9CC7EB"    # flatpak
SAGE_GREEN = "#A9C6A0"   # snap
LAVENDER = "#C2B3E8"     # nix / other / apk

# Brand + status colors
ACCENT = "#F2C489"       # soft amber: headers, wordmarks, highlights
SUCCESS = "#93C793"      # muted green
ERROR = "#E39A9A"        # muted rose
DIM = "dim"

# Status glyphs
CHECK = "✓"
CROSS = "✗"
ARROW = "▸"

# Source name -> tag color mapping
SOURCE_COLORS: dict[str, str] = {
    "apt": DUSTY_PEACH,
    "dnf": DUSTY_PEACH,
    "pacman": DUSTY_PEACH,
    "zypper": DUSTY_PEACH,
    "flatpak": SOFT_BLUE,
    "snap": SAGE_GREEN,
    "nix": LAVENDER,
    "apk": LAVENDER,
}


def color_for_source(source: str) -> str:
    """Return the pastel color for a source name; lavender for unknowns."""
    return SOURCE_COLORS.get(source.lower(), LAVENDER)
