"""APT adapter tests (subprocess fallback path with real captured output)."""

from __future__ import annotations

import output_samples as samples
from conftest import apt_routes, patch_dpkg_status, patch_runner, patch_which

from ins.adapters.apt_adapter import AptAdapter


def test_is_available_true_with_apt_and_dpkg_status(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apt_adapter", ["apt-get", "apt-cache", "dpkg-query"])
    patch_dpkg_status(monkeypatch, "ins.adapters.apt_adapter", present=True)
    assert AptAdapter().is_available() is True


def test_is_available_false_without_dpkg_status(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apt_adapter", ["apt-get", "apt-cache", "dpkg-query"])
    patch_dpkg_status(monkeypatch, "ins.adapters.apt_adapter", present=False)
    assert AptAdapter().is_available() is False


def test_is_available_false_without_apt(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apt_adapter", [])
    patch_dpkg_status(monkeypatch, "ins.adapters.apt_adapter", present=True)
    assert AptAdapter().is_available() is False


def test_search_fallback_parses_show_blocks(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apt_adapter", ["apt-get", "apt-cache", "dpkg-query"])
    patch_dpkg_status(monkeypatch, "ins.adapters.apt_adapter", present=True)
    calls = patch_runner(monkeypatch, "ins.adapters.apt_adapter", apt_routes())

    adapter = AptAdapter()
    results = adapter.search("vlc")

    assert [c[:2] for c in calls] == [["apt-cache", "search"], ["apt-cache", "show"]]
    vlc = next(r for r in results if r.id == "vlc")
    assert vlc.name == "vlc"
    assert vlc.version == "3.0.20-0+deb12u1"
    assert vlc.installed is True
    assert vlc.description == "multimedia player and streamer"
    assert vlc.size == 952 * 1024
    git = next(r for r in results if r.id == "git")
    assert git.installed is False
    assert git.description == "fast, scalable, distributed revision control system"


def test_list_installed_parses_dpkg_query(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apt_adapter", ["apt-get", "apt-cache", "dpkg-query"])
    patch_dpkg_status(monkeypatch, "ins.adapters.apt_adapter", present=True)
    calls = patch_runner(monkeypatch, "ins.adapters.apt_adapter", apt_routes())

    installed = AptAdapter().list_installed()

    assert calls[0][:2] == ["dpkg-query", "-W"]
    names = {i.id: i for i in installed}
    assert set(names) >= {"bash", "vlc", "zlib1g"}
    assert names["vlc"].version == "3.0.20-0+deb12u1"
    assert all(i.installed for i in installed)


def test_install_uses_privileged_apt_get(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apt_adapter", ["apt-get", "apt-cache", "dpkg-query"])
    patch_dpkg_status(monkeypatch, "ins.adapters.apt_adapter", present=True)
    calls = patch_runner(monkeypatch, "ins.adapters.apt_adapter", apt_routes())
    monkeypatch.setattr(
        "ins.adapters._subprocess.shutil.which",
        lambda name: "/usr/bin/pkexec" if name == "pkexec" else None,
    )

    assert AptAdapter().install("vlc") is True

    assert calls == [["pkexec", "apt-get", "-y", "install", "vlc"]]


def test_remove_uses_privileged_apt_get(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apt_adapter", ["apt-get", "apt-cache", "dpkg-query"])
    patch_dpkg_status(monkeypatch, "ins.adapters.apt_adapter", present=True)
    calls = patch_runner(monkeypatch, "ins.adapters.apt_adapter", apt_routes())
    monkeypatch.setattr(
        "ins.adapters._subprocess.shutil.which",
        lambda name: "/usr/bin/sudo" if name == "sudo" else None,
    )

    assert AptAdapter().remove("vlc") is True

    assert calls == [["sudo", "apt-get", "-y", "remove", "vlc"]]


def test_outdated_parses_upgradable_list(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apt_adapter", ["apt-get", "apt-cache", "dpkg-query"])
    patch_dpkg_status(monkeypatch, "ins.adapters.apt_adapter", present=True)
    calls = patch_runner(monkeypatch, "ins.adapters.apt_adapter", apt_routes())

    outdated = AptAdapter().outdated()

    assert calls[0][:3] == ["apt", "list", "--upgradable"]
    by_id = {i.id: i for i in outdated}
    assert set(by_id) == {"vlc", "git"}
    assert by_id["vlc"].version == "3.0.20-0+deb12u1"
    assert by_id["vlc"].available == "3.0.21-1"
    assert by_id["git"].available == "1:2.43.0-1"
    assert all(i.installed for i in outdated)


def test_upgrade_uses_privileged_apt_get_only_upgrade(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apt_adapter", ["apt-get", "apt-cache", "dpkg-query"])
    patch_dpkg_status(monkeypatch, "ins.adapters.apt_adapter", present=True)
    calls = patch_runner(monkeypatch, "ins.adapters.apt_adapter", apt_routes())
    monkeypatch.setattr(
        "ins.adapters._subprocess.shutil.which",
        lambda name: "/usr/bin/sudo" if name == "sudo" else None,
    )

    assert AptAdapter().upgrade("vlc") is True

    assert calls == [["sudo", "apt-get", "-y", "install", "--only-upgrade", "vlc"]]
