# ins — fish completions. Drop into ~/.config/fish/completions/ins.fish
# or add to your fish config's completions dir.

complete -c ins -s s -l search -d 'search for packages across all sources' -x \
    -a '(ins completions packages (commandline -ct) 2>/dev/null)'
complete -c ins -s i -l install -d 'install one or more packages' -x \
    -a '(ins completions packages (commandline -ct) 2>/dev/null)'
complete -c ins -s r -l remove -d 'remove one or more packages' -x \
    -a '(ins completions packages --installed (commandline -ct) 2>/dev/null)'
complete -c ins -s U -l upgrade -d 'upgrade one or more installed packages' -x \
    -a '(ins completions packages --installed (commandline -ct) 2>/dev/null)'
complete -c ins -l s -l source -d 'restrict the action to specific sources' -x \
    -a 'apt flatpak dnf pacman zypper snap nix apk'
complete -c ins -s u -l update -d 'update every detected source + tool updaters'
complete -c ins -s l -l list -d 'list installed packages grouped by source'
complete -c ins -s o -l outdated -d 'list packages with newer versions available'
complete -c ins -l dry-run -d 'show what would change without changing anything'
complete -c ins -s q -l quiet -d 'suppress informational output (errors still shown)'
complete -c ins -l no-progress -d 'run actions without the live progress bar'
complete -c ins -l json -d 'machine-readable JSON output (search, info)'
complete -c ins -s y -l yes -d 'assume yes to all prompts'
complete -c ins -s v -l version -d 'show version'
complete -c ins -n 'not __fish_seen_subcommand_from doctor info export bundle history undo completions' \
    -a doctor -d 'scan for duplicate installations across sources'
complete -c ins -n 'not __fish_seen_subcommand_from doctor info export bundle history undo completions' \
    -a info -d 'detailed view of a package'
complete -c ins -n 'not __fish_seen_subcommand_from doctor info export bundle history undo completions' \
    -a export -d 'write installed packages as a TOML manifest'
complete -c ins -n 'not __fish_seen_subcommand_from doctor info export bundle history undo completions' \
    -a bundle -d 'check or install a provisioning manifest'
complete -c ins -n 'not __fish_seen_subcommand_from doctor info export bundle history undo completions' \
    -a history -d 'show recent install/remove/upgrade transactions'
complete -c ins -n 'not __fish_seen_subcommand_from doctor info export bundle history undo completions' \
    -a undo -d 'reverse the last install or remove transaction'
complete -c ins -n 'not __fish_seen_subcommand_from doctor info export bundle history undo completions' \
    -a completions -d 'print a completion script or package names'
