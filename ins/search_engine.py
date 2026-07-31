"""Parallel multi-source search with dedup, fuzzy matching and ranking."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from ins.adapters._subprocess import AdapterError
from ins.adapters.base import SourceAdapter
from ins.models import AppInfo

DEFAULT_RESULT_CAP = 50
PER_SOURCE_TIMEOUT = 10.0
MIN_SCORE = 25.0
INSTALLED_BONUS = 5.0

# AppStream-style IDs -> canonical short names, so a Flatpak and a native
# package of the same app collapse into one group.
KNOWN_APP_IDS = {
    "org.mozilla.firefox": "firefox",
    "org.videolan.vlc": "vlc",
    "org.gimp.GIMP": "gimp",
    "org.inkscape.Inkscape": "inkscape",
    "org.gnome.gedit": "gedit",
    "org.kde.krita": "krita",
    "com.spotify.Client": "spotify",
    "org.telegram.desktop": "telegram-desktop",
    "com.discordapp.Discord": "discord",
    "org.audacityteam.Audacity": "audacity",
    "org.blender.Blender": "blender",
    "org.openshot.OpenShot": "openshot",
    "com.visualstudio.code": "code",
    "com.google.Chrome": "google-chrome",
    "org.libreoffice.LibreOffice": "libreoffice",
}

_TOKEN_RE = re.compile(r"[^a-z0-9]+")


class NoSourcesError(Exception):
    """Raised when there are no adapters to search."""


def normalize_key(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    return _TOKEN_RE.sub(" ", text.lower()).strip()


def canonical_key(info: AppInfo) -> str:
    base = KNOWN_APP_IDS.get(info.id.lower(), info.id)
    return normalize_key(base)


@dataclass(slots=True)
class GroupedResult:
    """One app merged across sources; highest-priority source is primary."""

    key: str
    name: str
    primary: AppInfo
    alternatives: list[AppInfo] = field(default_factory=list)
    score: float = 0.0
    stale: bool = False

    @property
    def also_via(self) -> list[str]:
        return [alt.source for alt in self.alternatives if alt.source != self.primary.source]

    @property
    def any_installed(self) -> bool:
        return self.primary.installed or any(alt.installed for alt in self.alternatives)


class SearchEngine:
    def __init__(
        self,
        adapters: list[SourceAdapter],
        *,
        cap: int = DEFAULT_RESULT_CAP,
        source_timeout: float = PER_SOURCE_TIMEOUT,
        cache=None,
        ttl: int = 3600,
    ):
        self._adapters = list(adapters)
        self._cap = cap
        self._timeout = source_timeout
        self._cache = cache
        self._ttl = ttl

    # ------------------------------------------------------------- searching

    def search(self, query: str, *, sources: list[str] | None = None) -> list[GroupedResult]:
        query = query.strip()
        if not query or not normalize_key(query):
            raise ValueError("search query must not be empty")
        adapters = [a for a in self._adapters if sources is None or a.name in sources]
        if not adapters:
            raise NoSourcesError("no package sources to search")

        per_source_limit = max(50, self._cap * 2)
        collected: dict[str, tuple[list[AppInfo], bool]] = {}
        with ThreadPoolExecutor(max_workers=len(adapters)) as pool:
            futures = {
                pool.submit(self._search_source, adapter, query, per_source_limit): adapter
                for adapter in adapters
            }
            for future in as_completed(futures):
                adapter = futures[future]
                try:
                    infos, stale = future.result()
                except AdapterError:
                    infos, stale = [], False
                if infos:
                    collected[adapter.name] = (infos, stale)

        groups = self._group(collected)
        self._score(groups, query)
        scored = [g for g in groups if g.score >= MIN_SCORE]
        scored.sort(key=lambda g: g.score, reverse=True)
        return scored[: self._cap]

    def _search_source(self, adapter: SourceAdapter, query: str, limit: int) -> tuple[list[AppInfo], bool]:
        if self._cache is not None:
            fresh = self._cache.get_fresh(adapter.name, query, self._ttl)
            if fresh is not None:
                return fresh, False
        try:
            infos = adapter.search(query, limit=limit)
        except AdapterError:
            if self._cache is not None:
                cached = self._cache.get_any(adapter.name, query)
                if cached is not None:
                    return cached, True
            raise
        if self._cache is not None:
            self._cache.put_results(adapter.name, query, infos)
        return infos, False

    # ------------------------------------------------------------- grouping

    def _group(self, collected: dict[str, tuple[list[AppInfo], bool]]) -> list[GroupedResult]:
        groups: dict[str, dict] = {}
        for adapter in self._adapters:
            if adapter.name not in collected:
                continue
            infos, stale = collected[adapter.name]
            for info in infos:
                info.source = adapter.name
                key = canonical_key(info)
                group = groups.get(key)
                if group is None:
                    group = {"name": info.name, "infos": [], "stale": False}
                    groups[key] = group
                group["infos"].append(info)
                group["stale"] = group["stale"] or stale

        ordered_adapters = {a.name: idx for idx, a in enumerate(self._adapters)}
        out: list[GroupedResult] = []
        for key, group in groups.items():
            infos = sorted(group["infos"], key=lambda i: ordered_adapters.get(i.source, 10**9))
            primary, *alternatives = infos
            out.append(
                GroupedResult(
                    key=key,
                    name=group["name"],
                    primary=primary,
                    alternatives=list(alternatives),
                    stale=group["stale"],
                )
            )
        return out

    # -------------------------------------------------------------- scoring

    def _score(self, groups: list[GroupedResult], query: str) -> None:
        q_norm = normalize_key(query)
        for group in groups:
            name_norm = normalize_key(group.name)
            desc_norm = normalize_key(group.primary.description)
            ratio = fuzz.ratio(q_norm, name_norm)
            partial = fuzz.partial_ratio(q_norm, desc_norm)
            popularity = max(0.0, min(1.0, group.primary.popularity))
            score = 0.6 * ratio + 0.25 * partial + 0.15 * popularity * 100.0
            if group.any_installed:
                score += INSTALLED_BONUS
            group.score = round(score, 2)
