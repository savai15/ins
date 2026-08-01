# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-08-01

### Changed
- **Fake mode removed** — `INS_FAKE=1` and the bundled fake demo sources are
  gone; `ins` only ever talks to real package managers on the system. The
  test suite keeps a private, non-shipped test double under `tests/`.
- **Visual overhaul** — rounded bordered tables with accent titles and pastel
  source tags across search, list, outdated, info, doctor, and history;
  `✓` success / `✗` error status marks.
- **Interactive picker removed** — bare `ins` no longer opens the
  type-to-filter search UI; it now prints a good-looking command list
  (grouped into search & install / maintain / share / options, in the
  rounded-box style) and exits 0. Every action takes an explicit flag or
  subcommand. The picker module (`ins/picker.py`) is gone.
- **Search results stay scannable** — capped at 20 results (was 50) with
  one-line descriptions, so `ins -s vlc` no longer prints a wall of rows.
- **Typo search works on real sources** — apt only matches literally, so
  `ins -s vcl` missed `vlc`; the apt adapter now fuzzy-matches against the
  local package-name list (`apt-cache pkgnames`) when no name hits, and
  transposition typos are boosted in ranking. Ubuntu's localized
  `Description-en` fields are parsed correctly too.
- **`fwupd` updater is opt-in** — `ins -u` runs only the no-password,
  user-level updaters (pipx, uv, rustup) by default. `fwupdmgr refresh` may
  prompt for admin rights (polkit) and downloads firmware metadata, so it now
  requires `enable = ["fwupd"]` in `[updaters]`.
- **apt search fixed on real distros** — `apt-cache search` lines are parsed
  as `name - description` (Ubuntu format) instead of being fed whole lines to
  `apt-cache show`; the python-apt path no longer relies on the removed
  `Cache.search()` API.
- **INS_FAKE-free sandboxing** — real tool updaters (`fwupdmgr`, `pipx`, …)
  can no longer fire (or pop polkit auth dialogs) during tests; accidental
  real subprocess calls in the suite fail loudly instead.
- Quiet `BrokenPipeError` handling when output is piped (e.g. `ins -l | head`).

### Fixed
- `ins -u` summary line styling; doctor/list/outdated/info tables keep their
  column alignment with the new frames.
- **Doctor never removes the real app for Ubuntu snap-transition packages** —
  apt ships empty wrappers for firefox/thunderbird/chromium-browser that only
  install the matching snap (version marker `1snap`, "Installs <name> snap…").
  `ins doctor` used to treat the wrapper + snap as a duplicate and, keeping the
  higher-priority apt copy, removed the snap — the actual browser. These stubs
  are now detected, skipped, and reported as `note:` lines (and listed under
  `transition_stubs` in `--json`), so no removal is offered for them.
- **`ins doctor --dry-run` is scan-only** — it renders the duplicate table and
  health summary but never prompts for or performs removals.
- **Junk search queries no longer return fuzzy noise** — the apt typo fallback
  scored match density only against the candidate name, so long garbage
  queries (`ins -s zzzzqqqq`) matched unrelated packages (`zaz`, `qrq`).
  Density is now `min(overlap/len(query), overlap/len(name))`, real typos
  still rank first, and junk queries return "no results found".
- **Cache schema bumped to v2** so stale pre-fix search results can't linger;
  the cache re-seeds automatically on the next run.

## [0.2.0] - 2026-07-31

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
- `--dry-run` — transaction previews for `-i`, `-r`, `-u`, and `-U`
  (versions, sizes, per-source update counts; `--json` supported)
- Transaction history — every install/remove/upgrade is recorded in the cache
  (`ins history [n]`, default 20; `--json` supported)
- `ins undo` — reverses the last install or remove transaction (removes what
  was installed, reinstalls what was removed), with a package-state check
  before acting
- `-q/--quiet` — suppress success messages (errors still shown)
- `--no-progress` — run without the live progress bar
- `--json` output for `ins doctor` (duplicates, sources, cache stats) and
  `ins -u` (per-source update counts)
- Tool updaters in `ins -u` — pipx (`upgrade-all`), uv (`tool upgrade --all`),
  rustup (`update`), and fwupd (`refresh`; firmware flashing stays interactive)
  auto-detected alongside package sources; counted per updater
- Custom updaters from `[updaters.custom]` in the config — any command
  (`name = ["cmd", "arg", ...]`), reported as "ran" when update counts are
  unknown; `[updaters] disable = [...]` turns off builtins
- `ins completions bash|zsh|fish` — print completion scripts on demand
- `ins completions packages [--installed] <prefix>` — package-name completion
  source; bash/zsh/fish scripts now complete package names for `-i`, `-s`,
  `-r`, `-U`, and `info`
- Man page (`docs/ins.1`, installed to `share/man/man1`)
- CI — GitHub Actions: pytest on Python 3.11/3.12/3.13 + ruff lint
- Ruff lint config; the whole codebase now passes `ruff check` clean

### Planned
- Extended `ins -u`: fwupd device updates, more tool updaters
- Package-name shell completions for more shells (nushell, elvish)

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
