#compdef ins
# ins — zsh completions. Add to fpath and run compinit, e.g.:
#   fpath+=(/path/to/completions) && compinit

_ins() {
  local -a subcommands sources
  subcommands=(doctor info)
  sources=(apt flatpak dnf pacman zypper snap nix apk)

  if (( CURRENT == 2 )); then
    _describe 'command' subcommands
    compadd -- -s -i -r --s -u -y --json -v -h
    return
  fi

  case $words[2] in
    info)
      compadd -a sources
      ;;
    doctor)
      compadd -- -s -i -r --s -u -y --json -v -h
      ;;
    *)
      compadd -- -s -i -r --s -u -y --json -v -h
      compadd -a sources
      ;;
  esac
}

compdef _ins ins
