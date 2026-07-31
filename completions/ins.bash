# ins — bash completions. Source from ~/.bashrc:
#   source <(ins completions)  (once added)
# or:  source /path/to/completions/ins.bash

_ins_completions() {
    local cur prev
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    local flags="-s --search -i --install -r --remove --s --source -u --update -y --yes --json -v --version -h --help"
    local commands="doctor info"
    local sources="apt flatpak dnf pacman zypper snap nix apk"

    # value-completing options
    case "$prev" in
        --s|--source|-i|-r|-s)
            COMPREPLY=( $(compgen -W "$sources" -- "$cur") )
            return
            ;;
    esac

    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$commands $flags" -- "$cur") )
        return
    fi

    case "${COMP_WORDS[1]}" in
        info)
            COMPREPLY=( $(compgen -W "$sources" -- "$cur") )
            return
            ;;
        doctor)
            COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
            return
            ;;
    esac

    COMPREPLY=( $(compgen -W "$flags $sources" -- "$cur") )
}

complete -F _ins_completions ins
