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

<p align="center"><b>One command to find, install, and remove software on Linux</b> — no matter which package manager your distro ships.</p>

<p align="center">
  <img src="assets/ins-wave-top.svg" alt="" width="700">
</p>

<p align="center">
  <img src="assets/ins-terminal.svg" alt="ins -s vcl finds vlc; ins -i vlc installs it with live progress" width="700">
</p>

<p align="center">
  <img src="assets/ins-sources.svg" alt="apt, dnf, pacman, zypper, flatpak, snap, nix, apk" width="700">
</p>

## Features

- **8 package managers, one interface** — apt, dnf, pacman, zypper, flatpak, snap, nix, apk are auto-detected and merged, so the same app from multiple sources shows up once.
- **Typo-tolerant search** — `ins -s vcl` still finds `vlc`, with transposition typos boosted against your real local package lists.
- **Safe by default** — `pkexec` with `sudo` fallback, confirm prompts with sizes, `--dry-run` previews, `-y` for scripting.
- **`ins doctor` protects your system** — duplicate detection that understands Ubuntu snap-transition stubs (it will never delete your real firefox), and `--dry-run` scans without prompting.
- **Full lifecycle** — install, remove, update, list, outdated, upgrade, `info`, `export`, `bundle check/install`, `history`, `undo`.
- **Tool updaters** — `ins -u` also runs pipx, uv, rustup (fwupd and custom commands opt-in).
- **Scripting-friendly** — `--json`, `-q`, `--no-progress`, bash/zsh/fish completions, man page.
- **Offline-friendly** — local SQLite cache with TTL; stale results are marked, never fatal.

## Install

Requires Python 3.11+.

```bash
# one-line installer (pipx, falls back to pip --user)
curl -sSL https://raw.githubusercontent.com/savai15/ins/main/install.sh | bash

# or with pipx
pipx install git+https://github.com/savai15/ins

# or with pip
pip install --user git+https://github.com/savai15/ins
```

Optional inline icons in `ins info` (kitty / iTerm2 / WezTerm): `pipx inject ins term-image`

## Quick start

```text
$ ins -s vcl
'vcl'
╭───────────────────────────────────┬───────────────────────────────────────╮
│Package                            │Description                            │
├───────────────────────────────────┼───────────────────────────────────────┤
│vlc [apt] 3.0.23-1                 │multimedia player and streamer         │
│cxl [apt] 81-1ubuntu1              │provisioning for CXL device memory     │
╰───────────────────────────────────┴───────────────────────────────────────╯

$ ins -i vlc -y
✓ installed vlc from apt

$ ins -u
apt: up to date
snap: 2 update(s)
pipx: ran
✓ 2 packages updated across snap
```

Preview before touching anything (works for `-i`, `-r`, `-u`, `-U`, with `--json`):

```text
$ ins -i vlc --dry-run
would install vlc from apt (35.3 KB)
```

Provision a machine from a manifest:

```text
$ ins export manifest.toml          # snapshot: what's installed, per source
$ ins bundle check manifest.toml    # drift report (exit 1 if out of date)
$ ins bundle install manifest.toml  # install what's missing (prompts, -y to skip)
```

## Commands

| Command             | What it does                                        |
| ------------------- | --------------------------------------------------- |
| `ins`               | show the full command list, grouped by category     |
| `ins -s <q>`        | search all sources, merged + ranked                 |
| `ins -i <pkg>...`   | install one or more packages (`-y` to skip prompt)  |
| `ins -r <pkg>...`   | remove one or more packages                         |
| `ins -u`            | update every detected source's index + tool updaters  |
| `ins -l`            | list installed packages grouped by source          |
| `ins -o`            | list packages with newer versions available        |
| `ins -U <pkg>...`   | upgrade installed packages                         |
| `ins export [file]` | write installed packages as a TOML manifest         |
| `ins bundle check <file>` | compare a manifest against installed state    |
| `ins bundle install <file>` | install what the manifest is missing       |
| `ins info <pkg>`    | detail view: license, homepage, size per source     |
| `ins doctor`        | find + resolve duplicate installs                   |
| `ins history [n]`   | show the last n install/remove/upgrade transactions (default 20) |
| `ins undo`          | reverse the last install or remove transaction      |
| `ins completions <bash\|zsh\|fish\|packages>` | print a completion script or package names |
| `--source <src>...` | restrict any action to specific sources             |
| `--dry-run`         | preview install/remove/update/upgrade without changing anything |
| `--json`            | machine-readable output (search, info, list, outdated, bundle check, doctor, update, dry-run, history) |
| `-q / --quiet`      | suppress success messages and progress (errors still shown) |
| `--no-progress`     | run without the live progress bar                   |
| `-y / --yes`        | assume yes (scripting)                              |

## Supported sources

| Source   | Search            | Install/Remove          | Update            | Outdated              | Upgrade                 |
| -------- | ----------------- | ----------------------- | ----------------- | --------------------- | ----------------------- |
| apt      | python-apt or apt-cache | `apt-get -y` (pkexec/sudo) | `apt-get update` | `apt list --upgradable` | `apt-get install --only-upgrade` |
| flatpak  | `flatpak search`  | `flatpak install/uninstall --user` | `flatpak update --user` | `flatpak remote-ls --updates` | `flatpak update --user` |
| dnf      | `dnf search -q`   | `dnf install/remove -y`  | `dnf upgrade -y` | `dnf list --upgrades`  | `dnf upgrade -y`        |
| pacman   | `pacman -Ss`      | `pacman -S/-R --noconfirm` | `pacman -Sy`   | `pacman -Qu`           | `pacman -S --noconfirm` |
| zypper   | `zypper -q search`| `zypper -n install/remove` | `zypper -n refresh` | `zypper -q list-updates` | `zypper -n update`   |
| snap     | `snap find`       | `snap install/remove`    | `snap refresh`  | `snap refresh --list`  | `snap refresh`          |
| nix      | `nix search nixpkgs` | `nix-env -iA/-e`      | `nix-channel --update` | — (resolved at run time) | `nix-env -u`         |
| apk      | `apk search -d`   | `apk add/del`            | `apk update`    | `apk upgrade -s`       | `apk add -u`            |

Sources are auto-detected by tool presence and skipped when absent, so the
same command works on Ubuntu, Fedora, Arch, openSUSE, NixOS, and Alpine —
`ins -s vlc` just shows you `[apt]` or `[dnf]` or `[pacman]` depending on the
box. There is no demo mode: every source is a real package manager.

## Configuration

`ins` reads `~/.config/ins/config.toml` and works with sensible defaults out of
the box:

```toml
[sources]
priority = ["apt", "flatpak", "dnf", "pacman", "zypper", "snap", "nix", "apk"]

[cache]
enabled = true
ttl_seconds = 3600
max_entries = 5000

[updaters]
# built-in tool updaters to skip: pipx, uv, rustup
disable = []

# opt-in privileged/network updaters (e.g. fwupd — its metadata refresh
# can prompt for admin rights and downloads firmware metadata)
enable = ["fwupd"]

# extra update commands run by `ins -u` (name = argv list)
custom = { texlive = ["tlmgr", "update", "--all"] }
```

## Development

```bash
git clone https://github.com/savai15/ins && cd ins
pip install -e ".[dev]"
pytest -q        # 270 tests, all subprocess calls stubbed with real Linux output
ruff check .     # lint (CI enforces both on Python 3.11/3.12/3.13)
```

The test suite replays *real* captured package-manager output
(`tests/output_samples.py`) through a fake subprocess layer, so parsing is
verified against actual tool formats — no mocks of the system calls involved.

## License

<p align="center">
  <img src="assets/ins-wave-bottom.svg" alt="" width="700">
</p>

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Savai.
