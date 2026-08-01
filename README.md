<p align="center">
  <img src="assets/ins-header.svg" alt="ins — one command to install anything on linux" width="640">
</p>

<p align="center">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-3fb950">
  <img alt="CI" src="https://img.shields.io/github/actions/workflow/status/savai15/ins/ci.yml?branch=main&label=CI&color=3fb950">
  <img alt="Release" src="https://img.shields.io/github/v/release/savai15/ins?color=58a6ff">
  <img alt="Platform" src="https://img.shields.io/badge/Platform-Linux-2ea44f">
  <img alt="Code style" src="https://img.shields.io/badge/code%20style-ruff-D7FF64">
</p>

<p align="center">
  <img src="assets/ins-tagline.svg" alt="one command to find, install, remove — on linux" width="700">
</p>

<p align="center">
  <img src="assets/ins-terminal.svg" alt="ins -s vcl finds vlc; ins -i vlc installs it with live progress" width="700">
</p>

<p align="center">
  <img src="assets/ins-sources.svg" alt="apt, dnf, pacman, zypper, flatpak, snap, nix, apk" width="700">
</p>

## Features

<p align="center">
  <img src="assets/ins-features.svg" alt="features: 8 package managers, typo-tolerant search, safe by default, doctor protection, full lifecycle, tool updaters, scripting-friendly, offline cache, pretty UI" width="700">
</p>

## Install

Requires Python 3.11+.

<p align="center">
  <img src="assets/ins-install.svg" alt="install: one-line installer, pipx, or pip" width="700">
</p>

## Quick start

<p align="center">
  <img src="assets/ins-quickstart.svg" alt="quick start: search, install with progress, update" width="700">
</p>

```text
$ ins -i vlc --dry-run
would install vlc from apt (35.3 KB)

$ ins export manifest.toml          # snapshot: what's installed, per source
$ ins bundle check manifest.toml    # drift report (exit 1 if out of date)
$ ins bundle install manifest.toml  # install what's missing (prompts, -y to skip)
```

## Commands

<p align="center">
  <img src="assets/ins-commands.svg" alt="all commands: search, install, remove, update, list, outdated, upgrade, info, doctor, history, undo, export, bundle, dry-run, json, quiet" width="700">
</p>

## Supported sources

<p align="center">
  <img src="assets/ins-sources-table.svg" alt="supported sources table: apt, flatpak, dnf, pacman, zypper, snap, nix, apk" width="700">
</p>

Sources are auto-detected by tool presence and skipped when absent, so the
same command works on Ubuntu, Fedora, Arch, openSUSE, NixOS, and Alpine.
There is no demo mode: every source is a real package manager.

## Configuration

`ins` reads `~/.config/ins/config.toml` and works with sensible defaults out of
the box:

<p align="center">
  <img src="assets/ins-config.svg" alt="configuration: sources priority, cache TTL, updaters" width="700">
</p>

## Repos & activity

<p align="center">
  <img src="assets/ins-featured.svg" alt="featured repository: savai15/ins, Python, release v0.3.0, 270 tests, MIT license, contribution activity" width="700">
</p>

## Development

<p align="center">
  <img src="assets/ins-dev.svg" alt="development: pip install -e, pytest 270 passed, ruff clean, CI on 3.11/3.12/3.13" width="700">
</p>

The test suite replays *real* captured package-manager output
(`tests/output_samples.py`) through a fake subprocess layer, so parsing is
verified against actual tool formats — no mocks of the system calls involved.

## License

<p align="center">
  <img src="assets/ins-footer.svg" alt="MIT License © 2026 Savai" width="500">
</p>

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Savai.

---

*Every visual on this page is a handcrafted, self-contained animated SVG —
no external image services, nothing to break. Regenerate with
`python3 tools/gen_readme_svgs.py`.*
