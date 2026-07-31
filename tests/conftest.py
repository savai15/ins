"""Shared test helpers: subprocess stubbing and fake adapters."""

from __future__ import annotations

import importlib

import pytest

import output_samples
from ins.adapters._subprocess import CommandFailed
from ins.adapters.fake_adapter import FakeAdapter
from ins.cache import Cache
from ins.config import Config


class FakeProcess:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def make_runner(routes: list[tuple[list[str], int, str, str]]):
    """Stub for `run`/`run_privileged`: match cmd prefix -> canned response.

    Routes are (prefix, returncode, stdout, stderr). sudo/pkexec prefixes are
    ignored for matching (but kept in recorded calls). Honors `check=True`.
    """
    calls: list[list[str]] = []
    privilege = {"sudo", "pkexec"}

    def fake_run(cmd, *, timeout=60.0, check=True, input=None):
        full = list(cmd)
        calls.append(full)
        match = [c for c in full if c not in privilege]
        for prefix, rc, out, err in routes:
            if match[: len(prefix)] == list(prefix):
                if check and rc != 0:
                    raise CommandFailed(full, rc, out, err)
                return FakeProcess(rc, out, err)
        if check:
            raise CommandFailed(full, 1, "", f"no route for: {' '.join(full)}")
        return FakeProcess(1, "", f"no route for: {' '.join(full)}")

    return fake_run, calls


def patch_runner(monkeypatch, module: str, routes: list[tuple[list[str], int, str, str]]):
    """Install the stub as `run`/`run_privileged` (and stream variants) on a module.

    `run_privileged*` keep the real pkexec/sudo prefixing logic (which reads
    `ins.adapters._subprocess.shutil.which` at call time), so privilege
    resolution is exercised for real. Stream stubs call `on_line` with each
    non-empty line of the routed stdout, matching the real contract.
    """
    fake_run, calls = make_runner(routes)
    monkeypatch.setattr(f"{module}.run", fake_run)

    from ins.adapters import _subprocess as sp

    def fake_run_privileged(cmd, *, timeout=300.0):
        return fake_run(sp.privileged(cmd), timeout=timeout)

    def fake_run_stream(cmd, on_line=None, *, timeout=60.0, check=True):
        proc = fake_run(cmd, timeout=timeout, check=check)
        if on_line is not None:
            for line in proc.stdout.splitlines():
                if line.strip():
                    on_line(line.strip())
        return proc

    def fake_run_privileged_stream(cmd, on_line=None, *, timeout=300.0):
        return fake_run_stream(sp.privileged(cmd), on_line=on_line, timeout=timeout)

    mod = importlib.import_module(module)
    for name, fn in (
        ("run_privileged", fake_run_privileged),
        ("run_stream", fake_run_stream),
        ("run_privileged_stream", fake_run_privileged_stream),
    ):
        if hasattr(mod, name):
            monkeypatch.setattr(f"{module}.{name}", fn)
    return calls


def patch_which(monkeypatch, module: str, binaries: list[str], sudo: bool = True):
    """Simulate the presence (and optional sudo) of tools for is_available()."""
    def fake_which(name: str):
        if name in binaries:
            return f"/usr/bin/{name}"
        if name == "sudo" and sudo:
            return "/usr/bin/sudo"
        return None

    monkeypatch.setattr(f"{module}.shutil.which", fake_which)


def patch_dpkg_status(monkeypatch, module: str, present: bool = True):
    monkeypatch.setattr(f"{module}.os.path.exists", lambda p: p == "/var/lib/dpkg/status" and present)


def apt_routes() -> list[tuple[list[str], int, str, str]]:
    return [
        (["apt-cache", "search", "--names-only"], 0, output_samples.APT_CACHE_SEARCH, ""),
        (["apt-cache", "show"], 0, output_samples.APT_CACHE_SHOW, ""),
        (["dpkg-query", "-W"], 0, output_samples.DPKG_QUERY_W, ""),
        (["apt-get"], 0, "", ""),
    ]


def flatpak_routes() -> list[tuple[list[str], int, str, str]]:
    return [
        (["flatpak", "search", "--columns=application,version,branch,remotes,description"], 0, output_samples.FLATPAK_SEARCH, ""),
        (["flatpak", "search", "--columns=application,remotes"], 0, output_samples.FLATPAK_SEARCH_REMOTES, ""),
        (["flatpak", "list", "--user"], 0, output_samples.FLATPAK_LIST_USER, ""),
        (["flatpak", "list", "--system"], 0, output_samples.FLATPAK_LIST_SYSTEM, ""),
        (["flatpak", "install"], 0, "", ""),
        (["flatpak", "uninstall"], 0, "", ""),
    ]


@pytest.fixture(autouse=True)
def _clean_fake_state(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    from ins.adapters import fake_adapter

    fake_adapter._STATE.clear()
    yield
    fake_adapter._STATE.clear()


@pytest.fixture
def fake_pair() -> list[FakeAdapter]:
    return [FakeAdapter("fake"), FakeAdapter("fake2")]


@pytest.fixture
def fake_env(monkeypatch, tmp_path):
    """INS_FAKE=1 + a temp cache db + default config, for CLI tests."""
    monkeypatch.setenv("INS_FAKE", "1")
    monkeypatch.setattr(
        "ins.cli.Cache",
        lambda enabled: Cache(tmp_path / "cache.db", enabled=enabled),
    )
    monkeypatch.setattr("ins.config.Config.load", lambda *a, **kw: Config())
    return tmp_path


__all__ = [
    "FakeProcess",
    "make_runner",
    "patch_runner",
    "patch_which",
    "patch_dpkg_status",
    "apt_routes",
    "flatpak_routes",
    "fake_pair",
    "fake_env",
]
