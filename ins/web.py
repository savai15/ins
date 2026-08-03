"""Web search fallback for ``ins -s <q> -w``: GitHub + install hints.

This is the first network code in the project and stays deliberately small:
stdlib ``urllib`` only, short timeouts, graceful degradation.  Install
resolution is (1) a small curated recipe table for known tools, (2) cheap
presence checks against npm / PyPI / crates.io and the latest GitHub
release.  Anything that would require running an untrusted remote script is
never auto-installed — ``resolve_install`` falls back to "open the repo page".
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from ins.adapters._subprocess import which
from ins.config import WebSettings

GITHUB_API = "https://api.github.com"
UA = "ins (github:savai15/ins)"

# Curated recipes for tools that ship via official curl scripts rather than
# any package source `ins` can reach.  Each entry is reviewed by hand; the
# command is printed verbatim and re-confirmed before it runs.
RECIPES: dict[str, dict[str, object]] = {
    "opencode": {
        "install": ["bash", "-c", "curl -fsSL https://opencode.ai/install | bash"],
        "display": "curl -fsSL https://opencode.ai/install | bash",
    },
    "uv": {
        "install": ["bash", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
        "display": "curl -LsSf https://astral.sh/uv/install.sh | sh",
    },
    "starship": {
        "install": ["bash", "-c", "curl -sS https://starship.rs/install.sh | sh"],
        "display": "curl -sS https://starship.rs/install.sh | sh",
    },
}


@dataclass(slots=True)
class WebResult:
    """One GitHub repository hit."""

    repo: str  # owner/name
    name: str  # short repo name
    description: str = ""
    url: str = ""
    stars: int = 0


@dataclass(slots=True)
class WebPage:
    results: list[WebResult]
    total: int = 0


@dataclass(slots=True)
class InstallPlan:
    """How a web result would be installed (or that we'd open the browser)."""

    repo: str
    url: str
    method: str  # recipe | npm | pipx | cargo | release | browser
    command: list[str] | None  # argv to run; None => open the repo page
    display: str


class WebError(Exception):
    """Web source unavailable: network failure, HTTP error, rate limit…"""

    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


def _http_get(url: str, *, timeout: float, token: str = "") -> bytes:
    headers = {
        "User-Agent": UA,
        "Accept": "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise WebError(f"HTTP {exc.code} from {url}", status=exc.code) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise WebError(f"request to {url} failed: {exc}") from exc


def _github_token(settings: WebSettings) -> str:
    return settings.token or os.environ.get("GITHUB_TOKEN") or ""


def _q(segment: str) -> str:
    return urllib.parse.quote(segment, safe="")


def search_github(query: str, *, settings: WebSettings, limit: int = 20, page: int = 1) -> WebPage:
    """Search GitHub repositories, paged. Raises :class:`WebError` on failure."""
    params = {
        "q": query,
        "per_page": str(max(1, min(limit, 100))),
        "page": str(max(1, page)),
    }
    url = f"{GITHUB_API}/search/repositories?{urllib.parse.urlencode(params)}"
    raw = _http_get(url, timeout=settings.timeout_seconds, token=_github_token(settings))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WebError("unparseable GitHub response") from exc
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise WebError("unexpected GitHub response shape")
    results = [
        WebResult(
            repo=str(item.get("full_name", "")),
            name=str(item.get("name", "")),
            description=str(item.get("description") or ""),
            url=str(item.get("html_url", "")),
            stars=int(item.get("stargazers_count") or 0),
        )
        for item in items
        if item.get("full_name")
    ]
    return WebPage(results, int(data.get("total_count") or 0))


def _json_exists(url: str, *, timeout: float, token: str = "") -> bool:
    """True when the URL returns 200 OK; any error just means 'not found'."""
    try:
        _http_get(url, timeout=timeout, token=token)
        return True
    except WebError:
        return False


def resolve_install(result: WebResult, settings: WebSettings) -> InstallPlan:
    """Find the least-invasive, most-verifiable way to install `result`."""
    name = result.name.lower()
    token = _github_token(settings)
    timeout = float(settings.timeout_seconds)

    recipe = RECIPES.get(name)
    if recipe is not None:
        command = list(recipe["install"])  # type: ignore[arg-type]
        return InstallPlan(result.repo, result.url, "recipe", command, str(recipe["display"]))

    if which("npm") and _json_exists(f"https://registry.npmjs.org/{_q(name)}", timeout=timeout):
        return InstallPlan(result.repo, result.url, "npm", ["npm", "install", "-g", name], f"npm install -g {name}")
    if which("pipx") and _json_exists(f"https://pypi.org/pypi/{_q(name)}/json", timeout=timeout):
        return InstallPlan(result.repo, result.url, "pipx", ["pipx", "install", name], f"pipx install {name}")
    if which("cargo") and _json_exists(f"https://crates.io/api/v1/crates/{_q(name)}", timeout=timeout):
        return InstallPlan(result.repo, result.url, "cargo", ["cargo", "install", name], f"cargo install {name}")

    release = None
    if which("curl"):
        try:
            raw = _http_get(
                f"{GITHUB_API}/repos/{result.repo}/releases/latest",
                timeout=timeout,
                token=token,
            )
            release = json.loads(raw)
        except (WebError, json.JSONDecodeError):
            release = None
    if isinstance(release, dict):
        asset = _pick_asset(release)
        if asset is not None:
            return _release_plan(result, asset)

    return InstallPlan(result.repo, result.url, "browser", None, f"open {result.url}")


_BINARY_SUFFIXES = (".deb", ".AppImage")
_SKIP_SUFFIXES = (".sig", ".asc", ".sha256", ".sha512")


def _pick_asset(release: dict) -> str | None:
    """Choose the most installable direct asset URL, or None."""
    assets = release.get("assets") or []
    candidates = [a for a in assets if isinstance(a, dict) and a.get("browser_download_url")]
    direct = [
        a for a in candidates
        if not any(a["name"].lower().endswith(sk) for sk in _SKIP_SUFFIXES)
    ]
    for suffix in _BINARY_SUFFIXES:
        for asset in direct:
            if asset["name"].lower().endswith(suffix):
                return str(asset["browser_download_url"])
    for asset in direct:
        name = str(asset.get("name", "")).lower()
        if "/" not in name and not any(name.endswith(s) for s in (".zip", ".tar.gz", ".tgz", ".tar.xz", ".gz")):
            return str(asset["browser_download_url"])
    return None


def _release_plan(result: WebResult, asset_url: str) -> InstallPlan:
    """Build a `bash -c` install script that fetches one direct-release asset."""
    if asset_url.lower().rsplit("/", 1)[-1].endswith(".deb"):
        script = (
            f'd="$(mktemp -d)" && cd "$d" && curl -fsSL "{asset_url}" -o pkg.deb '
            f'&& sudo dpkg -i pkg.deb && echo installed pkg.deb'
        )
        return InstallPlan(
            result.repo,
            result.url,
            "release",
            ["bash", "-c", script],
            f'curl "{asset_url}" && sudo dpkg -i pkg.deb',
        )
    name = result.name.replace(" ", "-").replace("/", "-") or "app"
    script = (
        f'd="$(mktemp -d)" && cd "$d" && curl -fsSL "{asset_url}" -o "{name}" '
        f'&& mkdir -p "$HOME/.local/bin" && chmod +x "{name}" '
        f'&& mv "{name}" "$HOME/.local/bin/{name}" && echo installed "$HOME/.local/bin/{name}"'
    )
    return InstallPlan(
        result.repo,
        result.url,
        "release",
        ["bash", "-c", script],
        f'download "{asset_url}" -> ~/.local/bin/{name}',
    )