"""Search engine tests: dedup, ranking, typo tolerance, isolation, cache interplay."""

from __future__ import annotations

import pytest

from ins.adapters._subprocess import AdapterError
from ins.adapters.base import SourceAdapter
from ins.adapters.fake_adapter import FakeAdapter
from ins.models import AppInfo
from ins.search_engine import GroupedResult, NoSourcesError, SearchEngine, normalize_key


def test_dedup_merges_same_app_across_sources(fake_pair):
    engine = SearchEngine(fake_pair)
    results = engine.search("vlc")
    assert len(results) == 1
    group = results[0]
    assert group.primary.source == "fake"
    assert group.also_via == ["fake2"]
    assert group.primary.name == "vlc"
    assert group.key == "vlc"


def test_primary_follows_adapter_order():
    engine = SearchEngine([FakeAdapter("fake2"), FakeAdapter("fake")])
    group = engine.search("vlc")[0]
    assert group.primary.source == "fake2"
    assert group.also_via == ["fake"]


def test_exact_name_match_ranks_first(fake_pair):
    results = SearchEngine(fake_pair).search("git")
    assert results[0].name == "git"
    assert results[0].score >= 60.0


def test_description_match_surfaces_app(fake_pair):
    results = SearchEngine(fake_pair).search("media player")
    names = [r.name for r in results]
    assert "vlc" in names


def test_irrelevant_query_returns_nothing(fake_pair):
    assert SearchEngine(fake_pair).search("zzz-not-in-catalog") == []


def test_typo_tolerance(fake_pair):
    results = SearchEngine(fake_pair).search("vcl")
    assert len(results) == 1
    assert results[0].name == "vlc"


def test_installed_gets_boost(fake_pair):
    fake, fake2 = fake_pair
    fake.install("htop")
    fake2.install("tmux")
    engine = SearchEngine(fake_pair)
    results = {r.name: r for r in engine.search("htop")}
    htop = results["htop"]
    assert htop.any_installed is True
    base = SearchEngine([FakeAdapter("fake3"), FakeAdapter("fake4")]).search("htop")[0]
    assert htop.score > base.score


def test_source_filter(fake_pair):
    engine = SearchEngine(fake_pair)
    results = engine.search("vlc", sources=["fake2"])
    assert len(results) == 1
    assert results[0].primary.source == "fake2"
    assert results[0].also_via == []


def test_no_sources_raises():
    with pytest.raises(NoSourcesError):
        SearchEngine([]).search("vlc")


def test_failing_source_does_not_kill_search():
    class BrokenAdapter(SourceAdapter):
        name = "broken"
        priority = 1

        def is_available(self):
            return True

        def search(self, query, limit=25):
            raise AdapterError("boom")

        def install(self, package_id):
            raise AdapterError("boom")

        def remove(self, package_id):
            raise AdapterError("boom")

        def list_installed(self):
            raise AdapterError("boom")

        def update(self, on_progress=None):
            return 0

        def upgrade(self, package_id, on_progress=None):
            return True

    engine = SearchEngine([BrokenAdapter(), FakeAdapter("fake")])
    results = engine.search("vlc")
    assert len(results) == 1
    assert results[0].primary.source == "fake"


def test_offline_fallback_uses_stale_cache(fake_pair, tmp_path):
    from ins.cache import Cache

    cache = Cache(tmp_path / "c.db")
    engine = SearchEngine(fake_pair, cache=cache, ttl=0)
    results = engine.search("vlc")
    assert results[0].primary.source == "fake"
    assert results[0].stale is False

    class DeadAdapter(SourceAdapter):
        name = "dead"
        priority = 1

        def is_available(self):
            return True

        def search(self, query, limit=25):
            raise AdapterError("network down")

        def install(self, package_id):
            raise AdapterError()

        def remove(self, package_id):
            raise AdapterError()

        def list_installed(self):
            raise AdapterError()

        def update(self, on_progress=None):
            return 0

        def upgrade(self, package_id, on_progress=None):
            return True

    cache.put_results("dead", "vlc", [AppInfo(id="vlc", name="vlc", source="dead", description="cached copy")])
    engine = SearchEngine([DeadAdapter()], cache=cache, ttl=0)
    results = engine.search("vlc")
    assert len(results) == 1
    assert results[0].stale is True
    assert results[0].primary.source == "dead"


def test_fresh_cache_skips_live_query(fake_pair, tmp_path):
    from ins.cache import Cache

    cache = Cache(tmp_path / "c.db")
    cache.put_results("fake", "vlc", [AppInfo(id="vlc", name="vlc", source="fake", description="from cache")])

    class ExplodingAdapter(SourceAdapter):
        name = "fake"
        priority = 5

        def is_available(self):
            return True

        def search(self, query, limit=25):
            raise AdapterError("should not be called")

        def install(self, package_id):
            raise AdapterError()

        def remove(self, package_id):
            raise AdapterError()

        def list_installed(self):
            raise AdapterError()

        def update(self, on_progress=None):
            return 0

        def upgrade(self, package_id, on_progress=None):
            return True

    engine = SearchEngine([ExplodingAdapter()], cache=cache, ttl=3600)
    results = engine.search("vlc")
    assert len(results) == 1
    assert results[0].primary.description == "from cache"
    assert results[0].stale is False


def test_result_cap():
    class ManyAdapter(SourceAdapter):
        name = "many"
        priority = 1

        def is_available(self):
            return True

        def search(self, query, limit=25):
            return [AppInfo(id=f"pkg{i}", name=f"pkg{i}", description="x", source=self.name) for i in range(limit)]

        def install(self, package_id):
            return True

        def remove(self, package_id):
            return True

        def list_installed(self):
            return []

        def update(self, on_progress=None):
            return 0

        def upgrade(self, package_id, on_progress=None):
            return True

    engine = SearchEngine([ManyAdapter()], cap=3)
    results = engine.search("pkg")
    assert len(results) == 3


def test_canonical_key_maps_appstream_ids():
    flatpak_info = AppInfo(id="org.mozilla.firefox", name="Firefox", source="flatpak")
    apt_info = AppInfo(id="firefox", name="firefox", source="apt")
    assert normalize_key("org.mozilla.firefox") != "firefox"
    from ins.search_engine import canonical_key

    assert canonical_key(flatpak_info) == canonical_key(apt_info) == "firefox"


def test_grouped_result_also_via_excludes_primary():
    primary = AppInfo(id="vlc", name="vlc", source="apt")
    alternatives = [AppInfo(id="vlc", name="vlc", source="apt"), AppInfo(id="vlc", name="vlc", source="snap")]
    group = GroupedResult(key="vlc", name="vlc", primary=primary, alternatives=alternatives)
    assert group.also_via == ["snap"]
