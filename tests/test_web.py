"""web.py tests — mocked HTTP seam, no real network."""

from __future__ import annotations

import json

import pytest
from ins import web
from ins.config import WebSettings


def _settings(**kw) -> WebSettings:
    return WebSettings(**kw)


def _search_json(*names: str) -> bytes:
    items = [
        {
            "full_name": f"owner/{n}",
            "name": n,
            "description": f"{n} description",
            "html_url": f"https://github.com/owner/{n}",
            "stargazers_count": 42,
        }
        for n in names
    ]
    return json.dumps({"total_count": len(items), "items": items}).encode()


class Stub:
    """Records URLs/tokens; serves canned bytes or raises WebError."""

    def __init__(self, resp: bytes = b"{}", error: web.WebError | None = None):
        self.urls: list[str] = []
        self.tokens: list[str] = []
        self._resp = resp
        self._error = error

    def __call__(self, url, *, timeout, token=""):
        self.urls.append(url)
        self.tokens.append(token)
        if self._error is not None:
            raise self._error
        return self._resp


# ------------------------------------------------------------- search


def test_search_github_parses_items(monkeypatch):
    stub = Stub(_search_json("opencode", "freebuf"))
    monkeypatch.setattr(web, "_http_get", stub)
    page = web.search_github("opencode", settings=_settings(), limit=20, page=1)
    assert page.total == 2
    assert [r.name for r in page.results] == ["opencode", "freebuf"]
    assert page.results[0].repo == "owner/opencode"
    assert page.results[0].stars == 42


def test_search_github_passes_paging_params(monkeypatch):
    stub = Stub(_search_json("a", "b", "c", "d", "e"))
    monkeypatch.setattr(web, "_http_get", stub)
    web.search_github("x", settings=_settings(), limit=20, page=3)
    url = stub.urls[0]
    assert "per_page=20" in url
    assert "page=3" in url
    assert "q=x" in url


def test_search_github_clamps_page_params(monkeypatch):
    stub = Stub(_search_json("p0"))
    monkeypatch.setattr(web, "_http_get", stub)
    web.search_github("x", settings=_settings(), limit=500, page=0)
    assert "per_page=100" in stub.urls[0]
    assert "page=1" in stub.urls[0]


def test_search_github_sends_token(monkeypatch):
    stub = Stub(_search_json("a"))
    monkeypatch.setattr(web, "_http_get", stub)
    web.search_github("a", settings=_settings(token="sekret"))
    assert stub.tokens == ["sekret"]


def test_search_github_raises_on_bad_json(monkeypatch):
    monkeypatch.setattr(web, "_http_get", Stub(b"not json at all"))
    with pytest.raises(web.WebError):
        web.search_github("x", settings=_settings())


def test_search_github_raises_on_network_failure(monkeypatch):
    monkeypatch.setattr(web, "_http_get", Stub(error=web.WebError("timeout")))
    with pytest.raises(web.WebError):
        web.search_github("x", settings=_settings())


def test_search_github_raises_on_missing_items(monkeypatch):
    monkeypatch.setattr(web, "_http_get", Stub(b'{"total_count": 0}'))
    with pytest.raises(web.WebError, match="shape"):
        web.search_github("x", settings=_settings())


# ------------------------------------------------------------- resolve


@pytest.fixture
def no_bins(monkeypatch):
    monkeypatch.setattr(web, "which", lambda _b: None)


def test_resolve_recipe_first(no_bins, monkeypatch):
    def _bomb(*_a, **_k):
        raise AssertionError("recipe must not touch the network")

    monkeypatch.setattr(web, "_http_get", _bomb)
    plan = web.resolve_install(web.WebResult("opencode-ai/opencode", "opencode"), _settings())
    assert plan.method == "recipe"
    assert plan.command and plan.command[0] == "bash"
    assert "opencode" in plan.display


def test_resolve_npm(monkeypatch):
    monkeypatch.setattr(web, "which", lambda b: "/usr/bin/npm" if b == "npm" else None)
    monkeypatch.setattr(
        web, "_json_exists",
        lambda url, timeout: url.startswith("https://registry.npmjs.org/"),
    )
    plan = web.resolve_install(web.WebResult("o/foo", "foo"), _settings())
    assert plan.method == "npm"
    assert plan.command == ["npm", "install", "-g", "foo"]


def test_resolve_pipx(monkeypatch):
    monkeypatch.setattr(web, "which", lambda b: "/usr/bin/pipx" if b == "pipx" else None)
    monkeypatch.setattr(
        web, "_json_exists",
        lambda url, timeout: url.startswith("https://pypi.org/pypi/"),
    )
    plan = web.resolve_install(web.WebResult("o/bar", "bar"), _settings())
    assert plan.method == "pipx"
    assert plan.command == ["pipx", "install", "bar"]


def test_resolve_cargo(monkeypatch):
    monkeypatch.setattr(web, "which", lambda b: "/usr/bin/cargo" if b == "cargo" else None)
    monkeypatch.setattr(
        web, "_json_exists",
        lambda url, timeout: url.startswith("https://crates.io/"),
    )
    plan = web.resolve_install(web.WebResult("o/baz", "baz"), _settings())
    assert plan.method == "cargo"
    assert plan.command == ["cargo", "install", "baz"]


def test_resolve_browser_when_no_method(no_bins):
    plan = web.resolve_install(web.WebResult("o/nope", "nope", url="https://github.com/o/nope"), _settings())
    assert plan.method == "browser"
    assert plan.command is None
    assert plan.url == "https://github.com/o/nope"


def test_resolve_release_asset_appimage(monkeypatch):
    def serve(url, *, timeout, token=""):
        return json.dumps({
            "assets": [{"name": "foo-x86_64.AppImage", "browser_download_url": "https://dl/foo.AppImage"}]
        }).encode()

    monkeypatch.setattr(web, "which", lambda b: "/usr/bin/curl" if b == "curl" else None)
    monkeypatch.setattr(web, "_http_get", serve)
    plan = web.resolve_install(web.WebResult("o/foo", "foo"), _settings())
    assert plan.method == "release"
    assert "~/.local/bin/foo" in plan.display


def test_resolve_release_skips_sig_assets(monkeypatch):
    def serve(url, *, timeout=30, token=""):
        return json.dumps({"assets": [
            {"name": "bar", "browser_download_url": "https://x/bar"},
            {"name": "bar.sha256", "browser_download_url": "https://x/bar.sha256"},
        ]}).encode()

    monkeypatch.setattr(web, "which", lambda b: "/usr/bin/curl" if b == "curl" else None)
    monkeypatch.setattr(web, "_http_get", serve)
    plan = web.resolve_install(web.WebResult("o/bar", "bar"), _settings())
    assert "https://x/bar.sha256" not in plan.display


def test_pick_asset_prefers_deb():
    release = {"assets": [
        {"name": "a.AppImage", "browser_download_url": "https://x/a.AppImage"},
        {"name": "a.deb", "browser_download_url": "https://x/a.deb"},
    ]}
    assert web._pick_asset(release) == "https://x/a.deb"


def test_pick_asset_none_for_empty():
    assert web._pick_asset({"assets": []}) is None


def test_release_plan_deb_uses_dpkg():
    plan = web._release_plan(web.WebResult("o/a", "a"), "https://x/a.deb")
    assert "dpkg -i" in plan.display
    assert "sudo" in plan.command[-1]


def test_github_token_prefers_settings(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "envtok")
    assert web._github_token(_settings(token="cfgtok")) == "cfgtok"
    assert web._github_token(_settings()) == "envtok"