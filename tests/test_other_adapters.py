"""Zypper, Nix and APK adapter tests."""

from __future__ import annotations

import output_samples as samples
from conftest import patch_runner, patch_which

from ins.adapters.apk_adapter import ApkAdapter
from ins.adapters.nix_adapter import NixAdapter
from ins.adapters.zypper_adapter import ZypperAdapter


# ------------------------------------------------------------------ zypper

def test_zypper_is_available(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.zypper_adapter", ["zypper", "rpm"])
    assert ZypperAdapter().is_available() is True
    patch_which(monkeypatch, "ins.adapters.zypper_adapter", ["zypper"])
    assert ZypperAdapter().is_available() is False


def test_zypper_search_parses_table(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.zypper_adapter", ["zypper", "rpm"])
    calls = patch_runner(
        monkeypatch,
        "ins.adapters.zypper_adapter",
        [(["zypper", "-q", "search"], 0, samples.ZYPPER_SEARCH, "")],
    )

    results = ZypperAdapter().search("vlc")

    by_name = {r.name: r for r in results}
    assert calls[0][:3] == ["zypper", "-q", "search"]
    assert by_name["vlc"].description == "The portable version of VLC"
    assert by_name["vlc"].installed is True
    assert by_name["vlc-codecs"].installed is False


def test_zypper_install_uses_privileged(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.zypper_adapter", ["zypper", "rpm"])
    calls = patch_runner(
        monkeypatch,
        "ins.adapters.zypper_adapter",
        [(["zypper", "-n", "install"], 0, "", "")],
    )
    monkeypatch.setattr(
        "ins.adapters._subprocess.shutil.which",
        lambda name: "/usr/bin/pkexec" if name == "pkexec" else None,
    )

    assert ZypperAdapter().install("vlc") is True

    assert calls == [["pkexec", "zypper", "-n", "install", "vlc"]]


def test_zypper_remove_uses_privileged(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.zypper_adapter", ["zypper", "rpm"])
    calls = patch_runner(
        monkeypatch,
        "ins.adapters.zypper_adapter",
        [(["zypper", "-n", "remove"], 0, "", "")],
    )
    monkeypatch.setattr(
        "ins.adapters._subprocess.shutil.which",
        lambda name: "/usr/bin/pkexec" if name == "pkexec" else None,
    )

    assert ZypperAdapter().remove("vlc") is True

    assert calls == [["pkexec", "zypper", "-n", "remove", "vlc"]]


# -------------------------------------------------------------------- nix

def test_nix_is_available(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.nix_adapter", ["nix", "nix-env"])
    assert NixAdapter().is_available() is True
    patch_which(monkeypatch, "ins.adapters.nix_adapter", ["nix"])
    assert NixAdapter().is_available() is False
    patch_which(monkeypatch, "ins.adapters.nix_adapter", ["nix-env"])
    assert NixAdapter().is_available() is False


def test_nix_search_parses_attr_lines(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.nix_adapter", ["nix", "nix-env"])
    calls = patch_runner(
        monkeypatch,
        "ins.adapters.nix_adapter",
        [
            (["nix", "search", "nixpkgs"], 0, samples.NIX_SEARCH, ""),
            (["nix-env", "-q"], 0, samples.NIX_ENV_Q, ""),
        ],
    )

    results = NixAdapter().search("vlc")

    assert calls[0][:3] == ["nix", "search", "nixpkgs"]
    by_name = {r.name: r for r in results}
    assert by_name["vlc"].version == "3.0.20"
    assert by_name["vlc"].description == "VideoLAN Client"
    assert by_name["vlc"].installed is True
    assert by_name["vlc-nox"].installed is False
    assert by_name["vlc-nox"].description == "VideoLAN Client (without X support)"
    assert by_name["vlc-plugin"].description == "VLC plugin"


def test_nix_list_installed_splits_version_at_last_hyphen(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.nix_adapter", ["nix", "nix-env"])
    patch_runner(
        monkeypatch,
        "ins.adapters.nix_adapter",
        [(["nix-env", "-q"], 0, samples.NIX_ENV_Q, "")],
    )

    installed = NixAdapter().list_installed()

    by_id = {i.id: i for i in installed}
    assert by_id["vlc"].version == "3.0.20"
    assert by_id["htop"].version == "3.3.0"
    assert by_id["cura"].version == "5.7.0"
    assert all(i.installed for i in installed)


def test_nix_install_uses_user_level_nix_env(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.nix_adapter", ["nix", "nix-env"])
    calls = patch_runner(
        monkeypatch,
        "ins.adapters.nix_adapter",
        [(["nix-env", "-iA"], 0, "", "")],
    )

    assert NixAdapter().install("vlc") is True

    assert calls == [["nix-env", "-iA", "nixpkgs.vlc"]]


def test_nix_remove_uses_user_level_nix_env(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.nix_adapter", ["nix", "nix-env"])
    calls = patch_runner(
        monkeypatch,
        "ins.adapters.nix_adapter",
        [(["nix-env", "-e"], 0, "", "")],
    )

    assert NixAdapter().remove("vlc") is True

    assert calls == [["nix-env", "-e", "vlc"]]


# -------------------------------------------------------------------- apk

def test_apk_is_available(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apk_adapter", ["apk"])
    assert ApkAdapter().is_available() is True
    patch_which(monkeypatch, "ins.adapters.apk_adapter", [])
    assert ApkAdapter().is_available() is False


def test_zypper_outdated_parses_list_updates(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.zypper_adapter", ["zypper", "rpm"])
    calls = patch_runner(
        monkeypatch,
        "ins.adapters.zypper_adapter",
        [(["zypper", "-q", "list-updates"], 0, samples.ZYPPER_LIST_UPDATES, "")],
    )

    outdated = ZypperAdapter().outdated()

    assert calls[0][:3] == ["zypper", "-q", "list-updates"]
    by_id = {i.id: i for i in outdated}
    assert set(by_id) == {"vlc"}
    assert by_id["vlc"].version == "3.0.20-1.1"
    assert by_id["vlc"].available == "3.0.21-1.1"
    assert all(i.installed for i in outdated)


def test_zypper_upgrade_uses_privileged(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.zypper_adapter", ["zypper", "rpm"])
    calls = patch_runner(
        monkeypatch,
        "ins.adapters.zypper_adapter",
        [(["zypper", "-n", "update"], 0, "", "")],
    )
    monkeypatch.setattr(
        "ins.adapters._subprocess.shutil.which",
        lambda name: "/usr/bin/sudo" if name == "sudo" else None,
    )

    assert ZypperAdapter().upgrade("vlc") is True

    assert calls == [["sudo", "zypper", "-n", "update", "vlc"]]


def test_nix_upgrade_uses_user_level_nix_env(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.nix_adapter", ["nix", "nix-env"])
    calls = patch_runner(
        monkeypatch,
        "ins.adapters.nix_adapter",
        [(["nix-env", "-u"], 0, "", "")],
    )

    assert NixAdapter().upgrade("vlc") is True

    assert calls == [["nix-env", "-u", "vlc"]]


def test_apk_outdated_parses_simulated_upgrade(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apk_adapter", ["apk"])
    calls = patch_runner(
        monkeypatch,
        "ins.adapters.apk_adapter",
        [(["apk", "upgrade", "-s"], 0, samples.APK_UPGRADE_S, "")],
    )

    outdated = ApkAdapter().outdated()

    assert calls[0][:3] == ["apk", "upgrade", "-s"]
    by_id = {i.id: i for i in outdated}
    assert set(by_id) == {"vlc", "zlib"}
    assert by_id["vlc"].available == "3.0.21-r0"
    assert by_id["zlib"].available == "1.3.1-r2"
    assert all(i.installed for i in outdated)


def test_apk_upgrade_uses_privileged(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apk_adapter", ["apk"])
    calls = patch_runner(
        monkeypatch,
        "ins.adapters.apk_adapter",
        [(["apk", "add", "-u"], 0, "", "")],
    )
    monkeypatch.setattr(
        "ins.adapters._subprocess.shutil.which",
        lambda name: "/usr/bin/sudo" if name == "sudo" else None,
    )

    assert ApkAdapter().upgrade("vlc") is True

    assert calls == [["sudo", "apk", "add", "-u", "vlc"]]


def test_apk_search_parses_descriptions(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apk_adapter", ["apk"])
    calls = patch_runner(
        monkeypatch,
        "ins.adapters.apk_adapter",
        [
            (["apk", "search", "-d"], 0, samples.APK_SEARCH, ""),
            (["apk", "info", "-v"], 0, samples.APK_INFO_V, ""),
        ],
    )

    results = ApkAdapter().search("vlc")

    assert calls[0][:3] == ["apk", "search", "-d"]
    by_name = {r.name: r for r in results}
    assert by_name["vlc"].description == "VideoLAN Client (new version)"
    assert by_name["vlc"].installed is True
    assert by_name["vlc-qt"].installed is False


def test_apk_list_installed_splits_version(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apk_adapter", ["apk"])
    patch_runner(
        monkeypatch,
        "ins.adapters.apk_adapter",
        [(["apk", "info", "-v"], 0, samples.APK_INFO_V, "")],
    )

    installed = ApkAdapter().list_installed()

    by_id = {i.id: i for i in installed}
    assert by_id["musl"].version == "1.2.5-r0"
    assert by_id["vlc"].version == "3.0.20-r0"
    assert by_id["zlib"].version == "1.3.1-r1"


def test_apk_install_uses_privileged(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apk_adapter", ["apk"])
    calls = patch_runner(
        monkeypatch,
        "ins.adapters.apk_adapter",
        [(["apk", "add"], 0, "", "")],
    )
    monkeypatch.setattr(
        "ins.adapters._subprocess.shutil.which",
        lambda name: "/usr/bin/sudo" if name == "sudo" else None,
    )

    assert ApkAdapter().install("vlc") is True

    assert calls == [["sudo", "apk", "add", "vlc"]]


def test_apk_remove_uses_privileged(monkeypatch):
    patch_which(monkeypatch, "ins.adapters.apk_adapter", ["apk"])
    calls = patch_runner(
        monkeypatch,
        "ins.adapters.apk_adapter",
        [(["apk", "del"], 0, "", "")],
    )
    monkeypatch.setattr(
        "ins.adapters._subprocess.shutil.which",
        lambda name: "/usr/bin/sudo" if name == "sudo" else None,
    )

    assert ApkAdapter().remove("vlc") is True

    assert calls == [["sudo", "apk", "del", "vlc"]]
