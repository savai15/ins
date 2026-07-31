# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `ins -l` / `--list` — installed packages grouped by source (`--json` supported)
- `ins -o` / `--outdated` — installed → available version table per source,
  parsed from `apt list --upgradable`, `flatpak remote-ls --updates`,
  `dnf list --upgrades`, `pacman -Qu`, `zypper list-updates`,
  `snap refresh --list`, and `apk upgrade -s` (`--json` supported)
- `ins -U <pkg>...` — upgrade installed packages one at a time with the same
  confirm + live-progress flow as install (`apt-get install --only-upgrade`,
  `flatpak update --user`, `dnf upgrade`, `pacman -S`, `zypper update`,
  `snap refresh`, `apk add -u`, `nix-env -u`)
- `AppInfo.available` field for upgrade-target versions (cache-safe round trip)
- `ins export [file]` — snapshot installed packages as a TOML manifest
  (stdout when no file given)
- `ins bundle check <file>` — drift report (missing / version-mismatched /
  extra packages) with `--json` and a non-zero exit code when out of date
- `ins bundle install <file>` — install missing packages with confirm prompts
- Interactive picker — bare `ins` on a terminal opens a type-to-filter,
  arrow-key search/install UI (rich Live, termios/msvcrt raw keys)
- `--dry-run` — transaction previews for `-i`, `-r`, `-u`, and `-U`
  (versions, sizes, per-source update counts; `--json` supported)

### Planned
- Install/remove transaction history with undo
- Extended `ins -u`: pipx, uv, rustup, fwupd, and custom commands from config
- `-q/--quiet`, `--no-progress`, JSON output for doctor/update
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
