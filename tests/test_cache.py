"""Cache tests: round-trip, TTL, offline fallback, invalidation, installed state."""

from __future__ import annotations

import time

import pytest
from ins.cache import Cache
from ins.models import AppInfo

from fake_adapter import FakeAdapter


@pytest.fixture
def cache(tmp_path):
    return Cache(tmp_path / "cache.db")


def test_put_get_round_trip(cache):
    infos = [AppInfo(id="vlc", name="vlc", source="apt", version="3.0.20", size=100, installed=True)]
    cache.put_results("apt", "vlc", infos)

    fresh = cache.get_fresh("apt", "vlc", ttl=3600)
    assert fresh is not None
    assert fresh[0].id == "vlc"
    assert fresh[0].installed is True
    assert fresh[0].size == 100


def test_missing_key_returns_none(cache):
    assert cache.get_any("apt", "vlc") is None
    assert cache.get_fresh("apt", "vlc", ttl=3600) is None


def test_ttl_expiry(cache, monkeypatch):
    cache.put_results("apt", "vlc", [AppInfo(id="vlc", name="vlc", source="apt")])
    now = time.time()
    monkeypatch.setattr("ins.cache.time.time", lambda: now + 7200)

    assert cache.get_fresh("apt", "vlc", ttl=3600) is None


def test_eviction_prunes_oldest_beyond_max(tmp_path, monkeypatch):
    cache = Cache(tmp_path / "cache.db", max_entries=2)
    clock = [time.time()]

    def tick():
        clock[0] += 100
        return clock[0]

    monkeypatch.setattr("ins.cache.time.time", tick)
    for i in range(4):
        cache.put_results(
            "apt", f"q{i}", [AppInfo(id=f"p{i}", name=f"p{i}", source="apt")]
        )

    assert cache.stats()["entries"] == 2
    assert cache.get_any("apt", "q0") is None
    assert cache.get_any("apt", "q1") is None
    assert cache.get_any("apt", "q2") is not None
    assert cache.get_any("apt", "q3") is not None


def test_eviction_respects_max_entries_config(tmp_path):
    from ins.config import Config

    cfg = Config.from_dict({"cache": {"max_entries": 1}})
    cache = Cache(tmp_path / "cache.db", max_entries=cfg.cache.max_entries)
    cache.put_results("apt", "a", [AppInfo(id="a", name="a", source="apt")])
    cache.put_results("apt", "b", [AppInfo(id="b", name="b", source="apt")])
    assert cache.stats()["entries"] == 1
    assert cache.stats()["max_entries"] == 1


def test_invalidate_by_package_id(cache):
    cache.put_results("apt", "vlc", [AppInfo(id="vlc", name="vlc", source="apt")])
    cache.put_results("apt", "firefox", [AppInfo(id="firefox", name="firefox", source="apt")])

    cache.invalidate(package_id="vlc")

    assert cache.get_any("apt", "vlc") is None
    assert cache.get_any("apt", "firefox") is not None


def test_invalidate_respects_source_and_query(cache):
    cache.put_results("apt", "vlc", [AppInfo(id="vlc", name="vlc", source="apt")])
    cache.put_results("snap", "vlc", [AppInfo(id="vlc", name="vlc", source="snap")])

    cache.invalidate(package_id="vlc", source="apt")

    assert cache.get_any("apt", "vlc") is None
    assert cache.get_any("snap", "vlc") is not None

    cache.put_results("apt", "vlc2", [AppInfo(id="vlc2", name="vlc2", source="apt")])
    cache.invalidate(query="vlc2")
    assert cache.get_any("apt", "vlc2") is None


def test_invalidate_escapes_like_wildcards(cache):
    cache.put_results("apt", "lib_x", [AppInfo(id="lib_x", name="lib_x", source="apt")])

    cache.invalidate(package_id="libxx")
    assert cache.get_any("apt", "lib_x") is not None

    cache.invalidate(package_id="lib_x")
    assert cache.get_any("apt", "lib_x") is None


def test_clear(cache):
    cache.put_results("apt", "vlc", [AppInfo(id="vlc", name="vlc", source="apt")])
    cache.mark_installed("apt", "vlc", "3.0.20")
    cache.clear()
    assert cache.get_any("apt", "vlc") is None
    assert cache.get_installed() == []


def test_installed_lifecycle(cache):
    assert cache.get_installed() == []
    cache.mark_installed("apt", "vlc", "3.0.20")
    cache.mark_installed("flatpak", "org.videolan.VLC", "3.0.20")
    assert set(cache.get_installed()) == {("apt", "vlc", "3.0.20"), ("flatpak", "org.videolan.VLC", "3.0.20")}
    cache.mark_removed("apt", "vlc")
    assert cache.get_installed("apt") == []
    assert len(cache.get_installed("flatpak")) == 1


def test_refresh_installed_replaces_source_snapshot(cache):
    fake = FakeAdapter("fake")
    fake.install("vlc")
    fake.install("git")
    cache.refresh_installed([fake])
    assert set(cache.get_installed("fake")) == {("fake", "git", "2.45.2"), ("fake", "vlc", "3.0.20")}

    fake.remove("vlc")
    cache.refresh_installed([fake])
    assert set(cache.get_installed("fake")) == {("fake", "git", "2.45.2")}


def test_refresh_skips_failing_source(cache):
    class Broken:
        name = "broken"

        def list_installed(self):
            raise RuntimeError("boom")

    counts = cache.refresh_installed([Broken(), FakeAdapter("fake")])
    assert "broken" not in counts
    assert counts["fake"] == 0
    assert cache.get_installed() == []


def test_disabled_cache_does_nothing(tmp_path):
    cache = Cache(tmp_path / "cache.db", enabled=False)
    cache.put_results("apt", "vlc", [AppInfo(id="vlc", name="vlc", source="apt")])
    assert cache.get_any("apt", "vlc") is None
    assert cache.get_installed() == []
    assert not (tmp_path / "cache.db").exists()


def test_corrupt_entry_degrades_to_empty(cache):
    with cache._connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO search_cache(source, query, data, fetched_at) VALUES('apt', 'x', 'not-json', 0)"
        )
    assert cache.get_any("apt", "x") == []


def test_history_records_and_lists_newest_first(cache):
    cache.record("install", "apt", "vlc", "3.0.20")
    cache.record("remove", "apt", "vlc")
    cache.record("upgrade", "apt", "vlc")
    history = cache.history()
    assert len(history) == 3
    assert history[0]["action"] == "upgrade"
    assert history[0]["package"] == "vlc"
    assert history[2]["version"] == "3.0.20"
    assert all(row["ok"] == 1 for row in history)


def test_history_limit(cache):
    for i in range(5):
        cache.record("install", "apt", f"pkg{i}")
    assert len(cache.history(2)) == 2
    assert cache.history(2)[0]["package"] == "pkg4"


def test_undo_target_skips_undone_and_upgrades(cache):
    cache.record("install", "apt", "vlc")
    cache.record("install", "apt", "git")
    cache.record("upgrade", "apt", "git")
    target = cache.undo_target()
    assert target["package"] == "git"
    assert target["action"] == "install"

    cache.mark_undone(target["id"])
    assert cache.undo_target()["package"] == "vlc"

    cache.mark_undone(cache.undo_target()["id"])
    assert cache.undo_target() is None
