# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- `ins list` / `ins outdated` / `ins upgrade <pkg>` — list, inspect, and update
  individual packages across all sources
- `ins export` + `ins bundle install|check` — declarative machine provisioning
- Interactive search/install picker (type-to-filter, arrow keys)
- `--dry-run` transaction previews for install/remove/update
- Install/remove transaction history with undo
- Extended `ins -u`: pipx, uv, rustup, fwupd, and custom commands from config
- `-q/--quiet`, `--no-progress`, JSON output for doctor/update/list/outdated
- CI (pytest matrix + lint), man page, package-name shell completions

## [0.1.0] - 2026-07-31

### Added
- Universal search across apt, dnf, pacman, zypper, flatpak, snap, nix, and apk,
  deduplicated and ranked (typo-tolerant via rapidfuzz)
- `ins -s <query>` — parallel multi-source search with "also via" grouping
- `ins -i <pkg>...` — batch install with confirm prompts, download sizes, and
  live progress from the underlying package manager
- `ins -r <pkg>...` — batch remove with a dim-to-gone erase animation
- `ins -u` — update every detected source with a per-source summary
- `ins info <pkg>` — license, homepage, size, and install state per source
- `ins doctor` — duplicate-install detection and interactive resolution
- Local SQLite cache with TTL, offline fallback with stale marking
- `--json` machine-readable output for search and info
- Optional inline app icons for kitty / iTerm2 / WezTerm via `term-image`
- Bash, zsh, and fish completions
- One-line installer (`curl -sSL .../install.sh | bash`)
- 155 tests replaying real captured package-manager output
