"""Load/save `~/.config/ins/config.toml`."""

from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("~/.config/ins/config.toml").expanduser()

DEFAULT_SOURCE_PRIORITY = [
    "apt",
    "flatpak",
    "dnf",
    "pacman",
    "zypper",
    "snap",
    "nix",
    "apk",
]


@dataclass(slots=True)
class CacheSettings:
    enabled: bool = True
    ttl_seconds: int = 3600
    max_entries: int = 5000


@dataclass(slots=True)
class Config:
    """User configuration with sensible defaults.

    TOML layout::

        [sources]
        priority = ["apt", "flatpak", "snap"]

        [cache]
        enabled = true
        ttl_seconds = 3600
        max_entries = 5000
    """

    source_priority: list[str] = field(default_factory=lambda: list(DEFAULT_SOURCE_PRIORITY))
    cache: CacheSettings = field(default_factory=CacheSettings)

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load config from disk; returns defaults when missing or unreadable."""
        path = path or DEFAULT_CONFIG_PATH
        if not path.is_file():
            return cls()
        try:
            with path.open("rb") as fh:
                data = tomllib.load(fh)
        except (tomllib.TOMLDecodeError, OSError):
            return cls()
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> Config:
        sources = data.get("sources", {})
        cache = data.get("cache", {})
        priority = sources.get("priority")
        cfg = cls()
        if isinstance(priority, list) and priority:
            cfg.source_priority = [str(p) for p in priority]
        if isinstance(cache, dict):
            if "enabled" in cache:
                cfg.cache.enabled = bool(cache["enabled"])
            if "ttl_seconds" in cache:
                cfg.cache.ttl_seconds = int(cache["ttl_seconds"])
            if "max_entries" in cache:
                cfg.cache.max_entries = int(cache["max_entries"])
        return cfg

    def to_dict(self) -> dict:
        return {
            "sources": {"priority": self.source_priority},
            "cache": asdict(self.cache),
        }

    def save(self, path: Path | None = None) -> None:
        """Write config to disk, creating parent directories as needed."""
        import tomli_w

        path = path or DEFAULT_CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fh:
            tomli_w.dump(self.to_dict(), fh)

    def enabled_sources(self, available: list[str]) -> list[str]:
        """Priority-ordered sources from config that exist among `available`."""
        return [s for s in self.source_priority if s in available]
