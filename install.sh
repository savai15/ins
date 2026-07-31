#!/usr/bin/env bash
# ins — one-line installer.
#
#   curl -sSL https://raw.githubusercontent.com/savai15/ins/main/install.sh | bash
#
# Installs `ins` via pipx when available, falling back to `pip install --user`.

set -euo pipefail

REPO_URL="${INS_REPO_URL:-https://github.com/savai15/ins}"
TAG="${INS_TAG:-v0.1.0}"

log()  { printf '\033[1;32m%s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m%s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m%s\033[0m\n' "$*" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 || die "python3 is required but was not found"

install_with_pipx() {
    local pipx
    pipx="$(command -v pipx || true)"
    if [ -z "$pipx" ]; then
        warn "pipx not found — trying to install it..."
        if command -v pip3 >/dev/null 2>&1; then
            pip3 install --user pipx 2>/dev/null || \
                pip3 install --user --break-system-packages pipx
            pipx="$HOME/.local/bin/pipx"
        else
            die "pip3 not found; install pipx first (e.g. apt install pipx)"
        fi
    fi
    [ -x "$pipx" ] || pipx="$(command -v pipx || true)"
    "$pipx" install --force "git+${REPO_URL}@${TAG}" || {
        warn "git+${REPO_URL} failed — falling back to a bare git clone + pip install"
        install_with_pip
    }
    log "installed via pipx: $(command -v ins || echo "$HOME/.local/bin/ins")"
}

install_with_pip() {
    local tmp
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT
    git clone --depth 1 --branch "$TAG" "$REPO_URL" "$tmp/ins" || \
        git clone --depth 1 "$REPO_URL" "$tmp/ins"
    pip3 install --user "$tmp/ins" 2>/dev/null || \
        pip3 install --user --break-system-packages "$tmp/ins"
    log "installed via pip: $HOME/.local/bin/ins"
}

if command -v pipx >/dev/null 2>&1 || [ -x "$HOME/.local/bin/pipx" ]; then
    install_with_pipx
else
    install_with_pip
fi

log "done. 'ins' is ready — run 'ins --help' to get started."
if [ -d "$HOME/.local/bin" ] && ! echo ":$PATH:" | grep -q ":${HOME}/.local/bin:"; then
    warn "add ~/.local/bin to your PATH: export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
