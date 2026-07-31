# ins

> One command to find, install, and remove software on Linux — no matter which
> package manager your distro ships.

`ins` is a universal CLI that unifies **apt, dnf, pacman, zypper, flatpak, snap,
nix, and apk** behind one simple, beautiful interface. Stop memorizing eight
different commands; one tool does search, install, remove, update, duplicate
detection, and per-package detail views across every source on your system.

## Features

- **One interface for 8 sources** — auto-detects what your distro has
  (apt-get, dnf, pacman, zypper, flatpak, snap, nix-env, apk), then merges
  results so the same app from multiple sources shows up once.
- **Unified search** — parallel queries with typo tolerance
  (`ins -s vcl` still finds VLC), deduplicated and ranked by relevance +
  popularity, capped at 50 results.
- **Interactive picker** — bare `ins` on a terminal opens a type-to-filter,
  arrow-key search/install UI (ctrl-c to quit).
- **Safe install/remove** — `pkexec` with a `sudo` fallback, live progress
  from the real package-manager output, confirm-before-install with sizes
  (`-y` skips prompts for scripting).
- **`--dry-run`** — see exactly what install/remove/update/upgrade would do
  (versions, sizes, per-source counts) without touching the system.
- **`ins doctor`** — flags apps installed twice (e.g. `vlc` via apt *and*
  flatpak) and offers to clean up.
- **`ins info`** — license, homepage, size, version, and install state per
  source, in one glance.
- **`ins -u`** — updates every detected source in sequence with a summary.
- **`ins -l` / `ins -o` / `ins -U <pkg>...`** — list installed packages,
  see which have newer versions available, and upgrade them individually.
- **`ins export` / `ins bundle`** — declarative provisioning: dump what's
  installed to a TOML manifest, check drift, and reinstall it on a fresh box.
- **`ins history` / `ins undo`** — every install/remove/upgrade is recorded;
  `ins undo` reverses the last one (removes what you installed, reinstalls
  what you removed), with a state check before acting.
- **Quiet mode** — `-q` silences success messages (errors still print) and
  `--no-progress` drops the live progress bar for pipelines.
- **Offline-friendly** — local SQLite cache with TTL; stale results are marked
  instead of failing when a source is unreachable.
- **`--json`** — machine-readable output for scripting.
- **Pretty** — pastel-colored source tags, aligned tables, spinners, and an
  erase animation on remove.

## Install

Requires Python 3.11+.

```bash
# one-line installer (pipx, falls back to pip --user)
curl -sSL https://raw.githubusercontent.com/savai15/ins/main/install.sh | bash

# or, if you already use pipx
pipx install git+https://github.com/savai15/ins

# or with pip
pip install --user git+https://github.com/savai15/ins
```

Optional inline icons in `ins info` (kitty / iTerm2 / WezTerm only):

```bash
pipx inject ins term-image        # or: pip install --user 'ins[icons]'
```

Shell completions for bash / zsh / fish ship with the package:

```bash
# bash
echo 'source /usr/share/completions/bash/ins.bash' >> ~/.bashrc

# zsh
fpath+=(/usr/share/completions/zsh) && compinit

# fish
cp /usr/share/completions/fish/ins.fish ~/.config/fish/completions/
```

## Quick start

Just `ins` on a terminal — type to filter, arrows to move, enter to install:

```text
$ ins
▸ vlc [fake] 3.0.20          VLC media player - the portable version
  git [fake] 2.45.2           fast, scalable, distributed revision control
type to filter · ↑/↓ move · enter install · ctrl-c quit
```

Or search directly:

```text
$ ins -s vlc
'vlc'
Package                       Description
vlc [fake] 3.0.20 [installed] VLC media player - the portable version
also via: fake2
```

Typo-tolerant, deduplicated, ranked:

```text
$ ins -s vcl
'vcl'
Package                  Description
vlc [fake] 3.0.20        VLC media player - the portable version
also via: fake2
```

Install (batch works too), with live progress:

```text
$ ins -i vlc git -y
installed vlc from fake
installed git from fake
```

Remove with a dim→collapse→gone erase animation on real terminals:

```text
$ ins -r vlc -y
removed vlc from fake
```

Update everything, with a summary:

```text
$ ins -u
6 packages updated across fake, fake2
```

See what's installed and what has updates, then upgrade:

```text
$ ins -l
Installed packages
Package               Version
vlc [fake]            3.0.20

$ ins -o
Updates available
Package               Installed  Available
vlc [fake]            3.0.20     3.0.21

$ ins -U vlc -y
upgraded vlc from fake
```

Preview before touching anything (works for `-i`, `-r`, `-u`, `-U`, with `--json`):

```text
$ ins -i vlc --dry-run
would install vlc from fake (24.3 MB)
```

Provision a machine from a manifest:

```text
$ ins export manifest.toml          # snapshot: what's installed, per source
$ ins bundle check manifest.toml    # drift report (exit 1 if out of date)
$ ins bundle install manifest.toml  # install what's missing (prompts, -y to skip)
```

Detail view per source:

```text
$ ins info vlc
vlc
VLC media player - the portable version
Source     Version    Size State         License Homepage
[fake]     3.0.20  24.3 MB installed     GPL-2.0 https://example.org/apps/vlc
[fake2]    3.0.20  24.3 MB not installed GPL-2.0 https://example.org/apps/vlc
```

Duplicate check + resolution:

```text
$ ins doctor
Duplicate installations
Package Installed via  Versions
vlc     [fake] [fake2] 3.0.20, 3.0.20
sources: 2/10 detected (fake, fake2)
cache: 4 entries, 0.03 MB (.../ins/cache.db)
config: ~/.config/ins/config.toml
Remove 'vlc' from fake2? [y/N]
```

JSON for scripts:

```json
$ ins -s vlc --json
{
  "query": "vlc",
  "results": [
    {
      "name": "vlc",
      "source": "fake",
      "version": "3.0.20",
      "installed": true,
      "also_via": ["fake2"],
      "alternatives": [ ... ]
    }
  ]
}
```

## Commands

| Command             | What it does                                        |
| ------------------- | --------------------------------------------------- |
| `ins`               | interactive type-to-filter search/install picker    |
| `ins -s <q>`        | search all sources, merged + ranked                 |
| `ins -i <pkg>...`   | install one or more packages (`-y` to skip prompt)  |
| `ins -r <pkg>...`   | remove one or more packages                         |
| `ins -u`            | update every detected source's index               |
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
| `--s <source>`      | restrict any action to specific sources             |
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

Sources are auto-detected by tool presence and skipped when absent. The demo
sources `fake` / `fake2` (with `INS_FAKE=1`) power the test suite and let you
try every command with zero system changes:

```bash
INS_FAKE=1 ins -s vlc
```

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
```

## Development

```bash
git clone https://github.com/savai15/ins && cd ins
pip install -e ".[dev]"
pytest -q        # 244 tests, all subprocess calls stubbed with real Linux output
```

The test suite replays *real* captured package-manager output
(`tests/output_samples.py`) through a fake subprocess layer, so parsing is
verified against actual tool formats — no mocks of the system calls involved.

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Savai.
