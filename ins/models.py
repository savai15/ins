"""Shared data models used across all sources."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class AppInfo:
    """A normalized package/app description from any source.

    Every adapter returns these; the CLI never sees source-specific types.
    """

    id: str
    name: str
    description: str = ""
    source: str = ""
    version: str = ""
    available: str = ""
    size: int = 0
    installed: bool = False
    popularity: float = 0.0

    def to_dict(self) -> dict:
        """Plain dict for JSON caching."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> AppInfo:
        """Rebuild from :meth:`to_dict` output; unknown keys are ignored."""
        fields = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        return cls(**fields)

    @property
    def size_human(self) -> str:
        """Human-readable size (e.g. '12.4 MB'); empty string when unknown."""
        if self.size <= 0:
            return ""
        units = ["B", "KB", "MB", "GB", "TB"]
        value = float(self.size)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
            value /= 1024
        return f"{value:.1f} B"
