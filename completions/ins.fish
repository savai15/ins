# ins — fish completions. Drop into ~/.config/fish/completions/ins.fish
# or add to your fish config's completions dir.

complete -c ins -s s -l search -d 'search for packages across all sources' -x
complete -c ins -s i -l install -d 'install one or more packages' -x
complete -c ins -s r -l remove -d 'remove one or more packages' -x
complete -c ins -l s -l source -d 'restrict the action to specific sources' -x \
    -a 'apt flatpak dnf pacman zypper snap nix apk'
complete -c ins -s u -l update -d 'update every detected source'
complete -c ins -s y -l yes -d 'assume yes to all prompts'
complete -c ins -l json -d 'machine-readable JSON output (search, info)'
complete -c ins -s v -l version -d 'show version'
complete -c ins -n 'not __fish_seen_subcommand_from doctor info' -a doctor \
    -d 'scan for duplicate installations across sources'
complete -c ins -n 'not __fish_seen_subcommand_from doctor info' -a info \
    -d 'detailed view of a package'
