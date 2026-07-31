# ins — bash completions. Add to ~/.bashrc:
#   source <(ins completions bash)
# or:  source /path/to/completions/ins.bash

_ins_sources="apt flatpak dnf pacman zypper snap nix apk"

_ins_package_names() {
    local flag=""
    case "$1" in
        -r|--remove|-U|--upgrade) flag="--installed" ;;
    esac
    COMPREPLY=( $(compgen -W "$(ins completions packages $flag "$2" 2>/dev/null)" -- "$2") )
}

_ins_completions() {
    local cur prev
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    local flags="-s --search -i --install -r --remove --s --source -u --update -l --list -o --outdated -U --upgrade -y --yes --json --dry-run -q --quiet --no-progress -v --version -h --help"
    local commands="doctor info export bundle history undo completions"

    # value-completing options
    case "$prev" in
        --s|--source)
            COMPREPLY=( $(compgen -W "$_ins_sources" -- "$cur") )
            return
            ;;
        -i|--install|-s|--search|info)
            _ins_package_names "" "$cur"
            return
            ;;
        -r|--remove|-U|--upgrade)
            _ins_package_names "$prev" "$cur"
            return
            ;;
        bundle)
            COMPREPLY=( $(compgen -W "check install" -- "$cur") )
            return
            ;;
        completions)
            COMPREPLY=( $(compgen -W "bash zsh fish packages" -- "$cur") )
            return
            ;;
        history)
            COMPREPLY=( $(compgen -W "10 20 50" -- "$cur") )
            return
            ;;
    esac

    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$commands $flags" -- "$cur") )
        return
    fi

    COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
}

complete -F _ins_completions ins
