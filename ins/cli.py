"""CLI entry point — search/install/remove/update/doctor/info."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.live import Live
from rich.progress import Progress

from ins import __version__, theme
from ins.adapters import registry
from ins.adapters._subprocess import AdapterError
from ins.bundle import check as check_manifest
from ins.bundle import dumps as manifest_dumps
from ins.bundle import load_manifest
from ins.cache import Cache
from ins.config import Config, DEFAULT_CONFIG_PATH
from ins.renderer import render_duplicates, render_info, render_list, render_outdated, render_search_results
from ins.search_engine import NoSourcesError, SearchEngine, normalize_key

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
ProgressCallback = Callable[[str], None]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ins",
        description="A universal CLI package search/install tool for Linux",
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "-s", "--search",
        nargs="*", metavar="QUERY", dest="search",
        help="search for packages across all sources",
    )
    parser.add_argument(
        "-i", "--install",
        nargs="*", metavar="PKG", dest="install",
        help="install one or more packages",
    )
    parser.add_argument(
        "-r", "--remove",
        nargs="*", metavar="PKG", dest="remove",
        help="remove one or more packages",
    )
    parser.add_argument(
        "--s", "--source",
        nargs="*", metavar="SOURCE", dest="sources",
        help="restrict the action to specific sources",
    )
    parser.add_argument(
        "-u", "--update",
        action="store_true",
        help="update every detected source's package index",
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="list installed packages grouped by source",
    )
    parser.add_argument(
        "-o", "--outdated",
        action="store_true",
        help="list packages with newer versions available",
    )
    parser.add_argument(
        "-U", "--upgrade",
        nargs="*", metavar="PKG", dest="upgrade",
        help="upgrade one or more installed packages",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="assume yes to all prompts (for scripting)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="machine-readable JSON output (search, info)",
    )
    parser.add_argument(
        "command", nargs="?", choices=("doctor", "info", "export", "bundle"),
        help="doctor: scan for duplicate installs across sources; "
             "info <pkg>: detailed view of a package; "
             "export [file]: write installed packages as a TOML manifest; "
             "bundle check|install <file>: verify or apply a manifest",
    )
    parser.add_argument(
        "subject", nargs="?",
        metavar="PKG",
        help="package name for `ins info`; check/install for `ins bundle`",
    )
    parser.add_argument(
        "bundle_file", nargs="?",
        metavar="FILE",
        help="manifest path for `ins bundle`",
    )
    return parser


# --------------------------------------------------------------- helpers

def _build_context(args: argparse.Namespace) -> tuple[Config, list, Cache | None, list[str]]:
    config = Config.load()
    adapters, errors = _load_adapters(config, args.sources)
    cache = Cache(enabled=config.cache.enabled, max_entries=config.cache.max_entries)
    return config, adapters, cache, errors


def _load_adapters(config: Config, requested: list[str] | None) -> tuple[list, list[str]]:
    adapters = registry.detect_sources(config)
    if requested:
        available = {a.name for a in adapters}
        errors: list[str] = []
        for name in requested:
            if name in available:
                continue
            if name in registry.known_sources():
                errors.append(f"source '{name}' is not available on this system")
            else:
                errors.append(f"unknown source '{name}'")
        if errors:
            return [], errors
        adapters = [a for a in adapters if a.name in requested]
    return adapters, []


def _adapter_by_name(adapters: list, name: str):
    for adapter in adapters:
        if adapter.name == name:
            return adapter
    return None


def _confirm(prompt: str, args: argparse.Namespace) -> bool:
    if args.yes:
        return True
    try:
        answer = input(prompt)
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")


def _sanitize_line(line: str) -> str:
    """Strip ANSI codes, collapse whitespace, cap length for display."""
    text = _ANSI_RE.sub("", line).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:72]


def _run_with_progress(runner: Callable[[ProgressCallback], object], name: str, console: Console) -> object:
    """Run `runner(on_line)` while surfacing output lines in a Progress bar."""
    progress = Progress(console=console)
    task = progress.add_task(f"[dim]{name}[/dim]", total=None)
    last_line = ""

    def on_line(line: str) -> None:
        nonlocal last_line
        text = _sanitize_line(line)
        if text and text != last_line:
            last_line = text
            progress.update(task, description=f"[dim]{text}[/dim]")

    with progress:
        return runner(on_line)


def _erase_animation(console: Console, name: str) -> None:
    """Dim -> collapse -> gone, only on a real terminal."""
    if not console.is_terminal:
        return
    steps = [
        f"[dim]{name}[/dim]",
        f"[dim]{name[: max(1, len(name) // 2)]}[/dim]",
        f"[dim]{name[:1]}[/dim]",
        "",
    ]
    with Live(console=console) as live:
        for text in steps:
            live.update(text)
            time.sleep(0.12)


# ------------------------------------------------------------- commands

def _search_results_json(results, query: str) -> dict:
    return {
        "query": query,
        "results": [
            {
                "name": g.name,
                "source": g.primary.source,
                "version": g.primary.version,
                "description": g.primary.description,
                "size": g.primary.size,
                "installed": g.any_installed,
                "score": round(g.score, 4),
                "stale": g.stale,
                "also_via": g.also_via,
                "alternatives": [a.to_dict() for a in g.alternatives],
            }
            for g in results
        ],
    }


def cmd_search(args: argparse.Namespace) -> int:
    config, adapters, cache, errors = _build_context(args)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 2
    if not adapters:
        print("error: no package sources detected on this system", file=sys.stderr)
        return 1
    query = " ".join(args.search or []).strip()
    if not query:
        print("error: search requires a query", file=sys.stderr)
        return 2
    engine = SearchEngine(
        adapters,
        cache=cache,
        ttl=config.cache.ttl_seconds,
    )
    console = Console()
    sources = ", ".join(a.name for a in adapters)
    with console.status(f"[dim]searching '{query}' across {sources}…[/dim]"):
        try:
            results = engine.search(query)
        except NoSourcesError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    if not results:
        if args.json:
            print(json.dumps(_search_results_json(results, query), indent=2))
            return 0
        print(f"no results found for '{query}'")
        return 0
    if args.json:
        print(json.dumps(_search_results_json(results, query), indent=2))
        return 0
    render_search_results(console, query, results)
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    names = [n for n in (args.install or []) if n]
    if not names:
        print("error: install requires at least one package name", file=sys.stderr)
        return 2
    config, adapters, cache, errors = _build_context(args)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 2
    if not adapters:
        print("error: no package sources detected on this system", file=sys.stderr)
        return 1
    engine = SearchEngine(adapters, cache=cache, ttl=config.cache.ttl_seconds)
    rc = 0
    for name in names:
        try:
            results = engine.search(name, sources=[a.name for a in adapters])
        except NoSourcesError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        target = next((r for r in results if normalize_key(r.name) == normalize_key(name)), None)
        if target is None and results:
            target = results[0]
        if target is None:
            print(f"error: '{name}' not found in any source", file=sys.stderr)
            rc = 1
            continue
        info = target.primary
        if target.any_installed:
            print(f"'{info.name}' is already installed (via {info.source})")
            continue
        adapter = _adapter_by_name(adapters, info.source)
        if adapter is None:
            print(f"error: source '{info.source}' unavailable", file=sys.stderr)
            rc = 1
            continue
        size = f" ({info.size_human})" if info.size else ""
        if not _confirm(f"Install '{info.name}' from {info.source}{size}? [y/N] ", args):
            print(f"skipped {info.name}")
            continue
        try:
            _run_with_progress(
                lambda cb: adapter.install(info.id, on_progress=cb),
                info.name,
                Console(),
            )
        except AdapterError as exc:
            print(f"error: failed to install {info.name}: {exc}", file=sys.stderr)
            rc = 1
            continue
        if cache is not None:
            cache.invalidate(package_id=info.id, source=info.source)
            cache.mark_installed(info.source, info.id, info.version)
        print(f"installed {info.name} from {info.source}")
    return rc


def cmd_remove(args: argparse.Namespace) -> int:
    names = [n for n in (args.remove or []) if n]
    if not names:
        print("error: remove requires at least one package name", file=sys.stderr)
        return 2
    config, adapters, cache, errors = _build_context(args)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 2
    if not adapters:
        print("error: no package sources detected on this system", file=sys.stderr)
        return 1
    engine = SearchEngine(adapters, cache=cache, ttl=config.cache.ttl_seconds)
    rc = 0
    for name in names:
        target = None
        adapter = None
        try:
            results = engine.search(name, sources=[a.name for a in adapters])
        except NoSourcesError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        group = next((r for r in results if normalize_key(r.name) == normalize_key(name)), None)
        if group is not None:
            candidate = next((i for i in [group.primary, *group.alternatives] if i.installed), None)
            if candidate is not None:
                target = candidate
                adapter = _adapter_by_name(adapters, candidate.source)
        if target is None:
            for candidate_adapter in adapters:
                try:
                    installed = candidate_adapter.list_installed()
                except AdapterError:
                    continue
                for info in installed:
                    if info.id == name or normalize_key(info.name) == normalize_key(name):
                        target = info
                        adapter = candidate_adapter
                        break
                if target is not None:
                    break
        if target is None or adapter is None:
            print(f"error: '{name}' is not installed (or not found)", file=sys.stderr)
            rc = 1
            continue
        if not _confirm(f"Remove '{target.name}' from {target.source}? [y/N] ", args):
            print(f"skipped {target.name}")
            continue
        try:
            _run_with_progress(
                lambda cb: adapter.remove(target.id, on_progress=cb),
                target.name,
                Console(),
            )
        except AdapterError as exc:
            print(f"error: failed to remove {target.name}: {exc}", file=sys.stderr)
            rc = 1
            continue
        _erase_animation(Console(), target.name)
        if cache is not None:
            cache.invalidate(package_id=target.id, source=target.source)
            cache.mark_removed(target.source, target.id)
        print(f"removed {target.name} from {target.source}")
    return rc


def cmd_update(args: argparse.Namespace) -> int:
    config, adapters, cache, errors = _build_context(args)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 2
    if not adapters:
        print("error: no package sources detected on this system", file=sys.stderr)
        return 1
    console = Console()
    total = 0
    sources_ok: list[str] = []
    failed: list[str] = []
    for adapter in adapters:
        try:
            count = _run_with_progress(
                lambda cb: adapter.update(on_progress=cb),
                adapter.name,
                console,
            )
        except AdapterError as exc:
            print(f"error: {adapter.name}: {exc}", file=sys.stderr)
            failed.append(adapter.name)
            continue
        total += int(count or 0)
        sources_ok.append(adapter.name)
    if sources_ok:
        if total:
            console.print(
                f"{total} packages updated across {', '.join(sources_ok)}",
                style=theme.SUCCESS,
            )
        else:
            print("all sources up to date")
    if failed:
        print(f"error: {len(failed)} source(s) failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    config, adapters, cache, errors = _build_context(args)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 2
    if not adapters:
        print("error: no package sources detected on this system", file=sys.stderr)
        return 1
    installed = _scan_installed(adapters)
    installed.sort(key=lambda i: (i.source, i.name))
    if args.json:
        print(json.dumps({"installed": [i.to_dict() for i in installed]}, indent=2))
        return 0
    render_list(Console(), installed)
    return 0


def cmd_outdated(args: argparse.Namespace) -> int:
    config, adapters, cache, errors = _build_context(args)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 2
    if not adapters:
        print("error: no package sources detected on this system", file=sys.stderr)
        return 1
    rows: list = []
    for adapter in adapters:
        try:
            rows.extend(adapter.outdated())
        except AdapterError:
            print(f"warning: could not check {adapter.name} for updates", file=sys.stderr)
    rows.sort(key=lambda i: (i.source, i.name))
    if args.json:
        print(json.dumps({"outdated": [i.to_dict() for i in rows]}, indent=2))
        return 0
    render_outdated(Console(), rows)
    return 0


def cmd_upgrade(args: argparse.Namespace) -> int:
    names = [n for n in (args.upgrade or []) if n]
    if not names:
        print("error: upgrade requires at least one package name", file=sys.stderr)
        return 2
    config, adapters, cache, errors = _build_context(args)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 2
    if not adapters:
        print("error: no package sources detected on this system", file=sys.stderr)
        return 1
    engine = SearchEngine(adapters, cache=cache, ttl=config.cache.ttl_seconds)
    rc = 0
    for name in names:
        target = None
        adapter = None
        try:
            results = engine.search(name, sources=[a.name for a in adapters])
        except NoSourcesError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        group = next((r for r in results if normalize_key(r.name) == normalize_key(name)), None)
        if group is not None:
            candidate = next((i for i in [group.primary, *group.alternatives] if i.installed), None)
            if candidate is not None:
                target = candidate
                adapter = _adapter_by_name(adapters, candidate.source)
        if target is None:
            for candidate_adapter in adapters:
                try:
                    installed = candidate_adapter.list_installed()
                except AdapterError:
                    continue
                for info in installed:
                    if info.id == name or normalize_key(info.name) == normalize_key(name):
                        target = info
                        adapter = candidate_adapter
                        break
                if target is not None:
                    break
        if target is None or adapter is None:
            print(f"error: '{name}' is not installed (or not found)", file=sys.stderr)
            rc = 1
            continue
        if not _confirm(f"Upgrade '{target.name}' from {target.source}? [y/N] ", args):
            print(f"skipped {target.name}")
            continue
        try:
            _run_with_progress(
                lambda cb: adapter.upgrade(target.id, on_progress=cb),
                target.name,
                Console(),
            )
        except AdapterError as exc:
            print(f"error: failed to upgrade {target.name}: {exc}", file=sys.stderr)
            rc = 1
            continue
        if cache is not None:
            cache.invalidate(package_id=target.id, source=target.source)
            cache.mark_installed(target.source, target.id, "")
        print(f"upgraded {target.name} from {target.source}")
    return rc


# ------------------------------------------------------- info (ins info <pkg>)

def _icon_capable_terminal() -> bool:
    env = os.environ
    if env.get("KITTY_WINDOW_ID") or env.get("ITERM_SESSION_ID"):
        return True
    return env.get("TERM_PROGRAM") == "WezTerm"


def _find_local_icon(group) -> Path | None:
    """Best-effort: flatpak exports a real icon file for installed apps."""
    for info in [group.primary, *group.alternatives]:
        if info.source != "flatpak":
            continue
        data_home = os.environ.get("XDG_DATA_HOME")
        base = Path(data_home) if data_home else Path.home() / ".local" / "share"
        icon_name = info.id.split(".")[-1].lower()
        for size in ("512x512", "256x256", "128x128", "64x64"):
            candidate = (
                base / "flatpak" / "exports" / "share" / "icons" / "hicolor"
                / size / "apps" / f"{icon_name}.png"
            )
            if candidate.is_file():
                return candidate
    return None


def _render_icon(console: Console, group) -> None:
    """Optional inline icon for terminal emulators that support it."""
    if not console.is_terminal or not _icon_capable_terminal():
        return
    icon = _find_local_icon(group)
    if icon is None:
        return
    try:
        from term_image.image import from_file

        with console.status("[dim]rendering icon…[/dim]"):
            image = from_file(str(icon))
            console.print(image)
    except Exception:
        pass


def cmd_info(args: argparse.Namespace, name: str) -> int:
    config, adapters, cache, errors = _build_context(args)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 2
    if not adapters:
        print("error: no package sources detected on this system", file=sys.stderr)
        return 1
    engine = SearchEngine(adapters, cache=cache, ttl=config.cache.ttl_seconds)
    try:
        results = engine.search(name, sources=[a.name for a in adapters])
    except NoSourcesError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    group = next((r for r in results if normalize_key(r.name) == normalize_key(name)), None)
    if group is None and results:
        group = results[0]
    if group is None:
        print(f"error: '{name}' not found in any source", file=sys.stderr)
        return 1
    console = Console()
    extras: dict[str, dict[str, str]] = {}
    for info in [group.primary, *group.alternatives]:
        adapter = _adapter_by_name(adapters, info.source)
        if adapter is None:
            continue
        try:
            extra = adapter.info(info.id)
        except AdapterError:
            extra = None
        if extra:
            extras[info.source] = extra

    if args.json:
        payload = {
            "name": group.name,
            "sources": [
                {
                    "source": info.source,
                    "version": info.version,
                    "size": info.size,
                    "installed": info.installed,
                    "license": extras.get(info.source, {}).get("license"),
                    "homepage": extras.get(info.source, {}).get("homepage"),
                    "description": extras.get(info.source, {}).get("description")
                    or info.description,
                }
                for info in [group.primary, *group.alternatives]
            ],
        }
        print(json.dumps(payload, indent=2))
        return 0

    _render_icon(console, group)
    render_info(console, group, extras)
    return 0


# -------------------------------------------------------- doctor (ins doctor)

def _scan_installed(adapters: list) -> list:
    out: list = []
    with ThreadPoolExecutor(max_workers=min(8, len(adapters))) as pool:
        futures = {pool.submit(a.list_installed): a for a in adapters}
        for future, adapter in futures.items():
            try:
                out.extend(future.result(timeout=30))
            except (AdapterError, TimeoutError):
                print(f"warning: could not scan {adapter.name}", file=sys.stderr)
    return out


def _render_health(console: Console, adapters: list, cache, config) -> None:
    known = registry.known_sources()
    detected = [a.name for a in adapters]
    console.print(
        f"[bold]sources:[/bold] {len(detected)}/{len(known)} detected "
        f"({', '.join(detected) or 'none'})"
    )
    if cache is not None:
        stats = cache.stats()
        size_mb = stats["db_size"] / 1024 / 1024
        path = stats["path"]
        if len(path) > 48:
            path = f"...{path[-48:]}"
        console.print(
            f"[bold]cache:[/bold] {stats['entries']} entries, "
            f"{size_mb:.2f} MB [dim]({path})[/dim]"
        )
    console.print(f"[bold]config:[/bold] {DEFAULT_CONFIG_PATH}")


def cmd_doctor(args: argparse.Namespace) -> int:
    config, adapters, cache, errors = _build_context(args)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 2
    if not adapters:
        print("error: no package sources detected on this system", file=sys.stderr)
        return 1
    console = Console()
    with console.status("[dim]scanning installed packages…[/dim]"):
        installed = _scan_installed(adapters)

    groups: dict[str, list] = {}
    for info in installed:
        key = normalize_key(info.name) or normalize_key(info.id)
        if not key:
            continue
        groups.setdefault(key, []).append(info)

    duplicates = [
        (key, infos)
        for key, infos in sorted(groups.items())
        if len({i.source for i in infos}) > 1
    ]
    render_duplicates(console, duplicates)
    _render_health(console, adapters, cache, config)

    rc = 0
    for _key, infos in duplicates:
        ordered = [a.name for a in adapters]
        keep_source = min(
            (i.source for i in infos),
            key=lambda s: ordered.index(s) if s in ordered else 10**9,
        )
        for info in infos:
            if info.source == keep_source:
                continue
            adapter = _adapter_by_name(adapters, info.source)
            if adapter is None:
                continue
            if not _confirm(f"Remove '{info.name}' from {info.source}? [y/N] ", args):
                print(f"skipped {info.name} from {info.source}")
                continue
            try:
                _run_with_progress(
                    lambda cb: adapter.remove(info.id, on_progress=cb),
                    info.name,
                    Console(),
                )
            except AdapterError as exc:
                print(f"error: failed to remove {info.name} from {info.source}: {exc}", file=sys.stderr)
                rc = 1
                continue
            _erase_animation(Console(), info.name)
            if cache is not None:
                cache.invalidate(package_id=info.id, source=info.source)
                cache.mark_removed(info.source, info.id)
            print(f"removed {info.name} from {info.source}")
    return rc


# -------------------------------------------------------- bundle (ins export / ins bundle)

def cmd_export(args: argparse.Namespace, target: str | None) -> int:
    config, adapters, cache, errors = _build_context(args)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 2
    if not adapters:
        print("error: no package sources detected on this system", file=sys.stderr)
        return 1
    installed = _scan_installed(adapters)
    if target:
        path = Path(target)
        path.write_text(manifest_dumps(installed), encoding="utf-8")
        print(f"exported {len(installed)} package(s) to {path}")
    else:
        print(manifest_dumps(installed))
    return 0


def _bundle_report(args: argparse.Namespace, report: dict) -> int:
    console = Console()
    drift = bool(report["missing"] or report["mismatched"])
    if args.json:
        print(
            json.dumps(
                {
                    "missing": [list(pair) for pair in report["missing"]],
                    "mismatched": [
                        {"source": s, "package": p, "installed": i, "required": r}
                        for s, p, i, r in report["mismatched"]
                    ],
                    "extra": [list(pair) for pair in report["extra"]],
                },
                indent=2,
            )
        )
        return 1 if drift else 0
    if not drift:
        console.print(f"[{theme.SUCCESS}]bundle is up to date[/]")
        if report["extra"]:
            console.print(f"[dim]{len(report['extra'])} extra package(s) installed but not in manifest[/]")
        return 0
    for source, pkg in report["missing"]:
        console.print(f"[bold]{pkg}[/bold] missing ({source})")
    for source, pkg, got, want in report["mismatched"]:
        console.print(f"[bold]{pkg}[/bold] ({source}): installed {got}, manifest requires {want}")
    return 1


def _bundle_install(args: argparse.Namespace, report: dict, adapters: list, cache) -> int:
    console = Console()
    if not report["missing"] and not report["mismatched"]:
        console.print(f"[{theme.SUCCESS}]bundle is up to date[/]")
        return 0
    for source, pkg, got, want in report["mismatched"]:
        print(f"note: {pkg} ({source}) is {got}, manifest requires {want} — use `ins -U` to upgrade")
    rc = 0
    for source, pkg in report["missing"]:
        adapter = _adapter_by_name(adapters, source)
        if adapter is None:
            print(f"error: source '{source}' is not available on this system", file=sys.stderr)
            rc = 1
            continue
        if not _confirm(f"Install '{pkg}' from {source}? [y/N] ", args):
            print(f"skipped {pkg}")
            continue
        try:
            _run_with_progress(
                lambda cb: adapter.install(pkg, on_progress=cb),
                pkg,
                console,
            )
        except AdapterError as exc:
            print(f"error: failed to install {pkg}: {exc}", file=sys.stderr)
            rc = 1
            continue
        if cache is not None:
            cache.invalidate(package_id=pkg, source=source)
            cache.mark_installed(source, pkg, "")
        print(f"installed {pkg} from {source}")
    return rc


def cmd_bundle(args: argparse.Namespace, action: str | None, file_arg: str | None) -> int:
    if action not in ("check", "install"):
        print(
            "error: `ins bundle` requires an action: ins bundle <check|install> <file>",
            file=sys.stderr,
        )
        return 2
    if not file_arg:
        print(f"error: `ins bundle {action}` requires a manifest file", file=sys.stderr)
        return 2
    try:
        manifest = load_manifest(file_arg)
    except FileNotFoundError:
        print(f"error: manifest not found: {file_arg}", file=sys.stderr)
        return 2
    except (ValueError, OSError) as exc:
        print(f"error: invalid manifest {file_arg}: {exc}", file=sys.stderr)
        return 2
    config, adapters, cache, errors = _build_context(args)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 2
    if not adapters:
        print("error: no package sources detected on this system", file=sys.stderr)
        return 1
    installed = _scan_installed(adapters)
    report = check_manifest(manifest, installed)
    if action == "check":
        return _bundle_report(args, report)
    return _bundle_install(args, report, adapters, cache)


# ------------------------------------------------------------- dispatch

def dispatch(args: argparse.Namespace) -> int:
    chosen = []
    if args.command == "doctor":
        chosen.append("doctor")
    if args.command == "info":
        chosen.append("info")
    if args.command == "export":
        chosen.append("export")
    if args.command == "bundle":
        chosen.append("bundle")
    if args.search is not None:
        chosen.append("search")
    if args.install is not None:
        chosen.append("install")
    if args.remove is not None:
        chosen.append("remove")
    if args.update:
        chosen.append("update")
    if args.list:
        chosen.append("list")
    if args.outdated:
        chosen.append("outdated")
    if args.upgrade is not None:
        chosen.append("upgrade")
    if len(chosen) > 1:
        print(f"error: pick one action, got: {', '.join(chosen)}", file=sys.stderr)
        return 2
    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "info":
        if not args.subject:
            print("error: `ins info` requires a package name: ins info <pkg>", file=sys.stderr)
            return 2
        return cmd_info(args, args.subject)
    if args.command == "export":
        return cmd_export(args, args.subject)
    if args.command == "bundle":
        return cmd_bundle(args, args.subject, args.bundle_file)
    if "search" in chosen:
        return cmd_search(args)
    if "install" in chosen:
        return cmd_install(args)
    if "remove" in chosen:
        return cmd_remove(args)
    if "update" in chosen:
        return cmd_update(args)
    if "list" in chosen:
        return cmd_list(args)
    if "outdated" in chosen:
        return cmd_outdated(args)
    if "upgrade" in chosen:
        return cmd_upgrade(args)
    print(
        "error: no action given — use -s/--search, -i/--install, -r/--remove, "
        "-u/--update, -l/--list, -o/--outdated, -U/--upgrade, "
        "or `ins doctor` / `ins info <pkg>` / `ins export` / `ins bundle check|install <file>`",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return dispatch(args)


if __name__ == "__main__":
    sys.exit(main())
