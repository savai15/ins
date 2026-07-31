#compdef ins
# ins — zsh completions. Add to fpath and run compinit, e.g.:
#   fpath+=(/path/to/completions) && compinit

_ins() {
  local -a subcommands sources
  subcommands=(doctor info export bundle history undo completions)
  sources=(apt flatpak dnf pacman zypper snap nix apk)
  local flags=(-s -i -r -u -l -o -U --s -y --json --dry-run -q --no-progress --installed -v -h)

  if (( CURRENT == 2 )); then
    _describe 'command' subcommands
    compadd -- $flags
    return
  fi

  case $words[2] in
    info|-i|--install|-s|--search)
      compadd -- $(ins completions packages "$PREFIX" 2>/dev/null)
      ;;
    -r|--remove|-U|--upgrade)
      compadd -- $(ins completions packages --installed "$PREFIX" 2>/dev/null)
      ;;
    bundle)
      compadd -- check install
      ;;
    completions)
      compadd -- bash zsh fish packages
      ;;
    history)
      compadd -- 10 20 50
      ;;
    *)
      compadd -- $flags
      compadd -a sources
      ;;
  esac
}

compdef _ins ins
