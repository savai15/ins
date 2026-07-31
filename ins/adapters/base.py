"""Adapter interface — every package source implements this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from ins.models import AppInfo


class SourceAdapter(ABC):
    """Interface every source (apt, flatpak, ...) must implement."""

    name: str = ""
    priority: int = 100

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this source can be used on the current system."""

    @abstractmethod
    def search(self, query: str, limit: int = 25) -> list[AppInfo]:
        """Search the source for packages matching `query`."""

    @abstractmethod
    def install(
        self,
        package_id: str,
        on_progress: Callable[[str], None] | None = None,
    ) -> bool:
        """Install the package; return True on success.

        If `on_progress` is given, it is called with each output line the
        underlying tool prints (progress/stage text) as it appears.
        """

    @abstractmethod
    def remove(
        self,
        package_id: str,
        on_progress: Callable[[str], None] | None = None,
    ) -> bool:
        """Remove the package; return True on success."""

    @abstractmethod
    def update(self, on_progress: Callable[[str], None] | None = None) -> int:
        """Refresh the source's package index; return best-effort count of
        packages updated (0 when the source doesn't report a count)."""

    @abstractmethod
    def upgrade(
        self,
        package_id: str,
        on_progress: Callable[[str], None] | None = None,
    ) -> bool:
        """Upgrade one installed package to its latest available version."""

    def outdated(self) -> list[AppInfo]:
        """Installed packages with a newer version available.

        Returns [] when the source can't report updates (e.g. nix).
        """
        return []

    def info(self, package_id: str) -> dict[str, str] | None:
        """Optional: extra detail fields (license, homepage, description)
        for one package; None when the source can't provide them."""
        return None

    @abstractmethod
    def list_installed(self) -> list[AppInfo]:
        """List all installed packages from this source."""
