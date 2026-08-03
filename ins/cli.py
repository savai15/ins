"""CLI entry point — search/install/remove/update/doctor/info."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rich.box import ROUNDED
from rich.console import Console
from rich.live import Live
from rich.progress import Progress
from rich.table import Table

from ins import __version__, theme, web
from ins.adapters import registry
from ins.adapters._subprocess import AdapterError
from ins.adapters._subprocess import run as sp_run
from ins.bundle import check as check_manifest
from ins.bundle import dumps as manifest_dumps
from ins.bundle import load_manifest
from ins.cache import Cache
from ins.config import DEFAULT_CONFIG_PATH, Config
from ins.models import AppInfo
from ins.renderer import render_duplicates, render_info, render_list, render_outdated, render_search_results
from ins.search_engine import GroupedResult, NoSourcesError, SearchEngine, normalize_key

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
ProgressCallback = Callable[[str], None]

MAX_PAGE_SIZE = 20
MAX_PAGE_WINDOW = 200  # how far ahead we rank locally so paging can slice


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
        "--dry-run",
        action="store_true",
        help="show what would change without changing anything",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="suppress informational output (errors still shown)",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="run actions without the live progress bar",
    )
    parser.add_argument(
        "--installed",
        action="store_true",
        help="(completions) complete installed package names instead of catalog names",
    )
    parser.add_argument(
        "-w", "--web",
        action="store_true", dest="web",
        help="also search GitHub for repositories (with -s; web installs are not tracked by -l/-u)",
    )
    parser.add_argument(
        "--page",
        type=int, default=None, metavar="N", dest="page",
        help="show page N of search results (default 1)",
    )
    parser.add_argument(
        "--per-page", "--limit",
        type=int, default=None, metavar="N", dest="per_page",
        help=f"results per page (default {MAX_PAGE_SIZE}, max {MAX_PAGE_SIZE})",
    )
    parser.add_argument(
        "command", nargs="?", choices=("doctor", "info", "export", "bundle", "history", "undo", "completions"),
        help="doctor: scan for duplicate installs across sources; "
             "info <pkg>: detailed view of a package; "
             "export [file]: write installed packages as a TOML manifest; "
             "bundle check|install <file>: verify or apply a manifest; "
             "history [n]: show recent transactions; "
             "undo: reverse the last install/remove; "
             "completions <bash|zsh|fish|packages>: print a completion script or package names",
    )
    parser.add_argument(
        "subject", nargs="?",
        metavar="PKG",
        help="package name for `ins info`; check/install for `ins bundle`; count for `ins history`; shell or `packages` for `ins completions`",
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
            if name == "web":
                continue  # not an adapter; enabled by `-w`/`--source web` in commands
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


def _say(args: argparse.Namespace, text: str) -> None:
    if not args.quiet:
        print(text)


def _ok(args: argparse.Namespace, text: str) -> None:
    """Success line: ✓ + muted green on a terminal, plain text elsewhere."""
    if not args.quiet:
        Console().print(f"[{theme.SUCCESS}]{theme.CHECK}[/] {text}")


def _run_action(args: argparse.Namespace, runner: Callable[[ProgressCallback], object], name: str, console: Console | None = None) -> object:
    """Run `runner(on_line)` with a progress bar, or directly with --no-progress / -q / --json."""
    if args.no_progress or args.quiet or args.json:
        return runner(None)
    return _run_with_progress(runner, name, console or Console())


def _install_group(group, adapters: list, cache, args: argparse.Namespace) -> int:
    """Confirm and install one GroupedResult via its primary source."""
    info = group.primary
    if group.any_installed:
        _say(args, f"'{info.name}' is already installed (via {info.source})")
        return 0
    adapter = _adapter_by_name(adapters, info.source)
    if adapter is None:
        print(f"error: source '{info.source}' unavailable", file=sys.stderr)
        return 1
    size = f" ({info.size_human})" if info.size else ""
    if not _confirm(f"Install '{info.name}' from {info.source}{size}? [y/N] ", args):
        _say(args, f"skipped {info.name}")
        return 0
    try:
        _run_action(args, lambda cb: adapter.install(info.id, on_progress=cb), info.name)
    except AdapterError as exc:
        print(f"error: failed to install {info.name}: {exc}", file=sys.stderr)
        return 1
    if cache is not None:
        cache.invalidate(package_id=info.id, source=info.source)
        cache.mark_installed(info.source, info.id, info.version)
        cache.record("install", info.source, info.id, info.version)
    _ok(args, f"installed {info.name} from {info.source}")
    return 0


def _sanitize_line(line: str) -> str:
    """Strip ANSI codes, collapse whitespace, cap length for display."""
    text = _ANSI_RE.sub("", line).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:72]


def _run_with_progress(runner: Callable[[ProgressCallback], object], name: str, console: Console) -> object:
    """Run `runner(on_line)` while surfacing output lines in a Progress bar."""
    progress = Progress(console=console)
    task = progress.add_task(f"[bold {theme.ACCENT}]{name}[/]", total=None)
    last_line = ""

    def on_line(line: str) -> None:
        nonlocal last_line
        text = _sanitize_line(line)
        if text and text != last_line:
            last_line = text
            progress.update(task, description=f"[dim]{text}[/dim]")

    with progress:
        return runner(on_line)


def _erase_animation(console: Console, name: str, source: str = "") -> None:
    """Dim -> collapse -> gone, only on a real terminal."""
    if not console.is_terminal:
        return
    color = theme.color_for_source(source) if source else theme.ACCENT
    steps = [
        f"[{color}]{name}[/]",
        f"[{color}]{name[: max(1, len(name) // 2)]}[/]",
        f"[{color}]{name[:1]}[/]",
        "",
    ]
    with Live(console=console) as live:
        for text in steps:
            live.update(text)
            time.sleep(0.12)


# ------------------------------------------------------------- commands

def _search_results_json(
    results,
    query: str,
    *,
    page: int = 1,
    per_page: int = MAX_PAGE_SIZE,
    total: int | None = None,
    web_results: list[dict] | None = None,
) -> dict:
    return {
        "query": query,
        "page": page,
        "per_page": per_page,
        "total": total if total is not None else len(results),
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
        "web": web_results or [],
    }


def _web_requested(args) -> bool:
    sources = args.sources if args.sources is not None else []
    return bool(args.web) or "web" in sources


def _web_group(result: web.WebResult) -> GroupedResult:
    """Wrap a GitHub hit as a GroupedResult rendered under source tag `web`."""
    info = AppInfo(
        id=result.repo,
        name=result.name,
        description=result.description,
        source="web",
        version=f"★ {result.stars}" if result.stars else "",
        popularity=float(result.stars),
    )
    return GroupedResult(key=result.name.lower(), name=result.name, primary=info)


def _page_params(args) -> tuple[int, int]:
    per_page = max(1, min(args.per_page or MAX_PAGE_SIZE, MAX_PAGE_SIZE))
    page = max(1, args.page or 1)
    return page, per_page


def _page_header(page: int, pages: int, per_page: int, total: int) -> str:
    shown = min(total, page * per_page)
    return f"[dim]page {page} of {pages} · showing {shown} of {total} results[/dim]"


def _run_web_command(plan: web.InstallPlan) -> None:
    proc = sp_run(plan.command, check=False)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise AdapterError(f"command failed (exit {proc.returncode}): {detail[:200]}")


def _open_url(url: str) -> None:
    try:
        sp_run(["xdg-open", url], check=False)
    except OSError:
        print(f"open in your browser: {url}")


def _install_from_web(web_results: list[web.WebResult], config: Config, cache, args) -> int:
    """Offer to install web results shown on the current page; returns exit code."""
    if not web_results or args.json or args.dry_run or args.quiet:
        return 0
    for result in web_results:
        if not _confirm(f"Install '{result.name}' from web? [y/N] ", args):
            _say(args, f"skipped {result.name}")
            continue
        plan = web.resolve_install(result, config.web)
        if plan.command is None:
            if _confirm(f"Open {plan.url}? [y/N] ", args):
                _open_url(plan.url)
            return 0
        print(f"Plan: {plan.display}")
        if not _confirm("Run this command? [y/N] ", args):
            _say(args, f"skipped {result.name}")
            return 0
        try:
            _run_action(args, lambda _cb, p=plan: _run_web_command(p), result.name)
        except AdapterError as exc:
            print(f"error: failed to install {result.name}: {exc}", file=sys.stderr)
            return 1
        if cache is not None:
            cache.record("install", "web", result.name, "")
        _ok(args, f"installed {result.name} (web)")
        return 0
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    config, adapters, cache, errors = _build_context(args)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 2
    query = " ".join(args.search or []).strip()
    if not query:
        print("error: search requires a query", file=sys.stderr)
        return 2
    use_web = _web_requested(args)
    if args.web and not config.web.enabled:
        print("warning: web search is disabled (set `[web] enabled = true` in config)", file=sys.stderr)
        use_web = False
    if not adapters and not use_web:
        print("error: no package sources detected on this system", file=sys.stderr)
        return 1

    page, per_page = _page_params(args)
    console = Console()
    statesource = ", ".join(a.name for a in adapters)
    local_all: list[GroupedResult] = []
    if adapters:
        engine = SearchEngine(adapters, cache=cache, ttl=config.cache.ttl_seconds)
        with console.status(f"[dim]searching '{query}' across {statesource}…[/dim]"):
            try:
                local_all = engine.ranked(query, sources=[a.name for a in adapters], cap=MAX_PAGE_WINDOW)
            except NoSourcesError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1

    web_page: web.WebPage | None = None
    if use_web:
        with console.status(f"[dim]searching GitHub for '{query}'…[/dim]"):
            try:
                web_page = web.search_github(query, settings=config.web, limit=per_page, page=page)
            except web.WebError as exc:
                console.print(f"[dim]web search unavailable: {exc}[/dim]")

    web_results = list(web_page.results) if web_page else []
    start = (page - 1) * per_page
    page_local = local_all[start:start + per_page]
    shown = list(page_local) + [_web_group(r) for r in web_results]
    total = len(local_all) + (web_page.total if web_page else 0)
    pages = max(1, (total + per_page - 1) // per_page) if total > 0 else 1
    install_candidates = web_results  # offer installs for the first rendered page

    if not shown and not web_results:
        if args.json:
            payload = _search_results_json([], query, page=page, per_page=per_page, total=0)
            print(json.dumps(payload, indent=2))
            return 0
        print(f"no results found for '{query}'")
        return 0

    if args.json:
        web_json = [
            {
                "name": r.name,
                "repo": r.repo,
                "url": r.url,
                "description": r.description,
                "stars": r.stars,
            }
            for r in web_results
        ]
        payload = _search_results_json(
            page_local, query, page=page, per_page=per_page, total=total, web_results=web_json,
        )
        print(json.dumps(payload, indent=2))
        return 0

    if pages > 1:
        console.print(_page_header(page, pages, per_page, total))
    render_search_results(console, query, shown)

    if not args.json and not args.quiet and not args.yes and pages > 1:
        current = page
        while current < pages:
            try:
                answer = input("[dim]show next page? [y/N] [/dim]")
            except (EOFError, OSError):
                break
            if answer.strip().lower() not in ("y", "yes"):
                break
            current += 1
            start = (current - 1) * per_page
            wr_new = []
            if use_web:
                try:
                    wr_new = web.search_github(query, settings=config.web, limit=per_page, page=current).results
                except web.WebError:
                    wr_new = []
            next_groups = local_all[start:start + per_page] + [_web_group(r) for r in wr_new]
            console.print(_page_header(current, pages, per_page, total))
            render_search_results(console, query, next_groups)
    return _install_from_web(install_candidates, config, cache, args)


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
    preview_lines: list[str] = []
    preview_rows: list[dict] = []
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
        if args.dry_run:
            info = target.primary
            if target.any_installed:
                preview_lines.append(f"'{info.name}' is already installed (via {info.source}) — no action")
            else:
                size = f" ({info.size_human})" if info.size else ""
                preview_lines.append(f"would install {info.name} from {info.source}{size}")
            preview_rows.append(
                {
                    "name": info.name,
                    "source": info.source,
                    "version": info.version,
                    "size": info.size,
                    "installed": target.any_installed,
                }
            )
            continue
        rc |= _install_group(target, adapters, cache, args)
    if args.dry_run:
        if args.json:
            print(json.dumps({"dry_run": True, "action": "install", "packages": preview_rows}, indent=2))
        else:
            for line in preview_lines:
                print(line)
    return rc


def cmd_remove(args: argparse.Namespace) -> int:
    names = [n for n in (args.remove or []) if n]
    if not names:
        print("error: remove requires at least one package name", file=sys.stderr)
        return 2
    lines: list[str] = []
    rows: list[dict] = []
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
        if args.dry_run:
            version = f" ({target.version})" if target.version else ""
            lines.append(f"would remove {target.name} from {target.source}{version}")
            rows.append(
                {"name": target.name, "source": target.source, "version": target.version}
            )
            continue
        if not _confirm(f"Remove '{target.name}' from {target.source}? [y/N] ", args):
            _say(args, f"skipped {target.name}")
            continue
        try:
            _run_action(
                args,
                lambda cb, adapter=adapter, target=target: adapter.remove(target.id, on_progress=cb),
                target.name,
            )
        except AdapterError as exc:
            print(f"error: failed to remove {target.name}: {exc}", file=sys.stderr)
            rc = 1
            continue
        _erase_animation(Console(), target.name, target.source)
        if cache is not None:
            cache.invalidate(package_id=target.id, source=target.source)
            cache.mark_removed(target.source, target.id)
            cache.record("remove", target.source, target.id, target.version)
        _ok(args, f"removed {target.name} from {target.source}")
    if args.dry_run:
        if args.json:
            print(json.dumps({"dry_run": True, "action": "remove", "packages": rows}, indent=2))
        else:
            for line in lines:
                print(line)
    return rc


def cmd_update(args: argparse.Namespace) -> int:
    config, adapters, _cache, errors = _build_context(args)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 2
    if not adapters:
        print("error: no package sources detected on this system", file=sys.stderr)
        return 1
    from ins.updaters import CustomUpdater, detect_updaters

    # tool updaters are skipped when --s restricts the run to specific sources
    updaters = [] if args.sources else detect_updaters(config.updaters)
    if args.dry_run:
        payload: dict[str, int] = {}
        for adapter in adapters:
            try:
                count = len(adapter.outdated())
            except AdapterError:
                count = 0
            payload[adapter.name] = count
            if args.json:
                continue
            if count:
                print(f"would update {count} package(s) via {adapter.name}")
            else:
                print(f"{adapter.name}: up to date")
        for updater in updaters:
            payload[updater.name] = -1  # count unknown until run
            if not args.json:
                print(f"would update via {updater.name}")
        if args.json:
            print(json.dumps({"dry_run": True, "action": "update", "sources": payload}, indent=2))
        return 0
    console = Console()
    total = 0
    sources_ok: list[str] = []
    counts: dict[str, int] = {}
    failed: list[str] = []
    for adapter in adapters:
        try:
            count = _run_action(
                args,
                lambda cb, adapter=adapter: adapter.update(on_progress=cb),
                adapter.name,
                console,
            )
        except AdapterError as exc:
            print(f"error: {adapter.name}: {exc}", file=sys.stderr)
            failed.append(adapter.name)
            continue
        total += int(count or 0)
        counts[adapter.name] = int(count or 0)
        sources_ok.append(adapter.name)
    updater_counts: dict[str, int] = {}
    for updater in updaters:
        try:
            count = _run_action(
                args,
                lambda cb, updater=updater: updater.update(on_progress=cb),
                updater.name,
                console,
            )
        except AdapterError as exc:
            print(f"error: {updater.name}: {exc}", file=sys.stderr)
            failed.append(updater.name)
            continue
        updater_counts[updater.name] = int(count or 0)
        if args.json:
            continue
        if count:
            _say(args, f"{updater.name}: {count} update(s)")
        elif not isinstance(updater, CustomUpdater):
            _say(args, f"{updater.name}: up to date")
        else:
            _say(args, f"{updater.name}: ran")
    if args.json:
        print(json.dumps({"sources": counts, "updaters": updater_counts, "failed": failed, "total": total}, indent=2))
        return 1 if failed else 0
    if sources_ok:
        if total:
            if not args.quiet:
                console.print(
                    f"[{theme.SUCCESS}]{theme.CHECK}[/] {total} packages updated across {', '.join(sources_ok)}"
                )
        else:
            _say(args, "all sources up to date")
    if failed:
        print(f"error: {len(failed)} source(s) failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    _config, adapters, _cache, errors = _build_context(args)
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
    _config, adapters, _cache, errors = _build_context(args)
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
    rows: list[dict] = []
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
        if args.dry_run:
            available = ""
            try:
                for up in adapter.outdated():
                    if up.id == target.id:
                        available = up.available
                        break
            except AdapterError:
                pass
            rows.append(
                {"name": target.name, "source": target.source, "version": target.version, "available": available}
            )
            if args.json:
                continue
            if available:
                print(f"would upgrade {target.name} from {target.source} ({target.version or '?'} -> {available})")
            else:
                print(f"would upgrade {target.name} from {target.source}")
            continue
        if not _confirm(f"Upgrade '{target.name}' from {target.source}? [y/N] ", args):
            _say(args, f"skipped {target.name}")
            continue
        try:
            _run_action(
                args,
                lambda cb, adapter=adapter, target=target: adapter.upgrade(target.id, on_progress=cb),
                target.name,
            )
        except AdapterError as exc:
            print(f"error: failed to upgrade {target.name}: {exc}", file=sys.stderr)
            rc = 1
            continue
        if cache is not None:
            cache.invalidate(package_id=target.id, source=target.source)
            cache.mark_installed(target.source, target.id, "")
            cache.record("upgrade", target.source, target.id)
        _ok(args, f"upgraded {target.name} from {target.source}")
    if args.dry_run and args.json:
        print(json.dumps({"dry_run": True, "action": "upgrade", "packages": rows}, indent=2))
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


def _is_snap_transition_stub(info) -> bool:
    """True for Ubuntu's snap-transition apt packages (firefox, thunderbird,
    chromium-browser, …) — empty wrappers that only install the matching snap.
    Their version carries the `1snap` marker and/or their description says
    'Installs <name> snap…'. Treating them as real installs makes doctor
    'duplicates' point at the wrong copy and can remove the actual app."""
    if info.source != "apt":
        return False
    version = (info.version or "").lower()
    if "1snap" in version:
        return True
    desc = (info.description or "").lower()
    return "installs " in desc and " snap" in desc


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

    # Ubuntu ships snap-transition apt packages (e.g. firefox, chromium-browser,
    # thunderbird) that are empty wrappers installing the real snap. They look
    # like duplicates but are not: never treat them as the real install, and
    # never count them toward duplicate detection.
    stubs = [i for i in installed if _is_snap_transition_stub(i)]

    groups: dict[str, list] = {}
    for info in installed:
        if _is_snap_transition_stub(info):
            continue
        key = normalize_key(info.name) or normalize_key(info.id)
        if not key:
            continue
        groups.setdefault(key, []).append(info)

    duplicates = [
        (key, infos)
        for key, infos in sorted(groups.items())
        if len({i.source for i in infos}) > 1
    ]
    if args.json:
        payload = {
            "duplicates": [
                {
                    "name": infos[0].name,
                    "sources": [i.source for i in infos],
                    "versions": [i.version for i in infos],
                }
                for _key, infos in duplicates
            ],
            "transition_stubs": [
                {"name": s.name, "version": s.version} for s in stubs
            ],
            "sources": {
                "detected": [a.name for a in adapters],
                "known": len(registry.known_sources()),
            },
        }
        if cache is not None:
            stats = cache.stats()
            payload["cache"] = {k: v for k, v in stats.items() if k != "path"}
        print(json.dumps(payload, indent=2))
        return 0
    for stub in stubs:
        console.print(
            f"[{theme.DIM}]note: {stub.name}: apt copy is a snap-transition stub, "
            "not a real duplicate — skipped[/]"
        )
    render_duplicates(console, duplicates)
    _render_health(console, adapters, cache, config)
    if args.dry_run:
        return 0

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
                _say(args, f"skipped {info.name} from {info.source}")
                continue
            try:
                _run_action(
                    args,
                    lambda cb, adapter=adapter, info=info: adapter.remove(info.id, on_progress=cb),
                    info.name,
                )
            except AdapterError as exc:
                print(f"error: failed to remove {info.name} from {info.source}: {exc}", file=sys.stderr)
                rc = 1
                continue
            _erase_animation(Console(), info.name, info.source)
            if cache is not None:
                cache.invalidate(package_id=info.id, source=info.source)
                cache.mark_removed(info.source, info.id)
                cache.record("remove", info.source, info.id)
            _ok(args, f"removed {info.name} from {info.source}")
    return rc


# -------------------------------------------------------- bundle (ins export / ins bundle)

def cmd_history(args: argparse.Namespace) -> int:
    _config, _adapters, cache, errors = _build_context(args)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 2
    limit = 20
    if args.subject:
        try:
            limit = int(args.subject)
        except ValueError:
            print(f"error: invalid history size '{args.subject}'", file=sys.stderr)
            return 2
    records = [] if cache is None else cache.history(limit)
    if args.json:
        print(json.dumps({"history": records}, indent=2))
        return 0
    console = Console()
    if not records:
        console.print(f"[dim]{theme.ARROW} no transactions recorded yet[/]")
        return 0
    table = Table(
        box=ROUNDED,
        border_style="dim",
        title=f"[{theme.ACCENT}]transaction history[/]",
        header_style=f"bold {theme.ACCENT}",
        pad_edge=False,
        collapse_padding=True,
    )
    table.add_column("When")
    table.add_column("Action")
    table.add_column("Package")
    table.add_column("Source")
    table.add_column("Version")
    for record in records:
        table.add_row(record["ts"], record["action"], record["package"], record["source"], record["version"] or "—")
    console.print(table)
    return 0


def cmd_undo(args: argparse.Namespace) -> int:
    _config, adapters, cache, errors = _build_context(args)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 2
    if cache is None:
        print("error: no transaction history available", file=sys.stderr)
        return 1
    record = cache.undo_target()
    if record is None:
        _say(args, "nothing to undo")
        return 0
    action = record["action"]
    source = record["source"]
    package = record["package"]
    version = record["version"]
    adapter = _adapter_by_name(adapters, source)
    if adapter is None:
        print(f"error: cannot undo: source '{source}' is not available on this system", file=sys.stderr)
        return 1
    try:
        installed = {info.id for info in adapter.list_installed()}
    except AdapterError:
        print(f"error: cannot verify state of {source}", file=sys.stderr)
        return 1
    if action == "install":
        if package not in installed:
            print(f"error: cannot undo: '{package}' is no longer installed via {source}", file=sys.stderr)
            return 1
        prompt = f"Undo install: remove '{package}' from {source}? [y/N] "
    else:
        if package in installed:
            print(f"error: cannot undo: '{package}' is still installed via {source}", file=sys.stderr)
            return 1
        prompt = f"Undo remove: reinstall '{package}' from {source}? [y/N] "
    if not _confirm(prompt, args):
        _say(args, "skipped")
        return 0
    try:
        if action == "install":
            _run_action(args, lambda cb: adapter.remove(package, on_progress=cb), package)
            if cache is not None:
                cache.mark_removed(source, package)
                cache.invalidate(package_id=package, source=source)
            _ok(args, f"undid install of {package} from {source}")
        else:
            _run_action(args, lambda cb: adapter.install(package, on_progress=cb), package)
            if cache is not None:
                cache.invalidate(package_id=package, source=source)
                cache.mark_installed(source, package, version)
            _ok(args, f"undid remove of {package} from {source}")
    except AdapterError as exc:
        print(f"error: failed to undo: {exc}", file=sys.stderr)
        return 1
    cache.mark_undone(record["id"])
    return 0


def cmd_export(args: argparse.Namespace, target: str | None) -> int:
    _config, adapters, _cache, errors = _build_context(args)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 2
    if not adapters:
        print("error: no package sources detected on this system", file=sys.stderr)
        return 1
    installed = _scan_installed(adapters)
    if target:
        path = Path(target)
        try:
            path.write_text(manifest_dumps(installed), encoding="utf-8")
        except OSError as exc:
            print(f"error: could not write {path}: {exc.strerror or exc}", file=sys.stderr)
            return 1
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
        console.print(f"[{theme.SUCCESS}]{theme.CHECK}[/] bundle is up to date")
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
        console.print(f"[{theme.SUCCESS}]{theme.CHECK}[/] bundle is up to date")
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
            _run_action(
                args,
                lambda cb, adapter=adapter, pkg=pkg: adapter.install(pkg, on_progress=cb),
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
            cache.record("install", source, pkg)
        _ok(args, f"installed {pkg} from {source}")
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
    _config, adapters, cache, errors = _build_context(args)
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


# ------------------------------------------------------ completions (ins completions)

def _completion_script(shell: str) -> Path:
    """Locate a completion script: repo checkout first, installed data dirs as fallback."""
    here = Path(__file__).resolve().parent.parent
    for base in (here / "completions", Path(sys.prefix) / "share" / "completions"):
        candidate = base / f"ins.{shell}"
        if candidate.is_file():
            return candidate
    return here / "completions" / f"ins.{shell}"


def cmd_completions(args: argparse.Namespace) -> int:
    """`ins completions <bash|zsh|fish|packages> [prefix]`."""
    shell = args.subject
    if shell in ("bash", "zsh", "fish"):
        try:
            print(_completion_script(shell).read_text(encoding="utf-8"), end="")
        except OSError:
            print(f"error: completion script for {shell} not found", file=sys.stderr)
            return 1
        return 0
    if shell != "packages":
        print("error: `ins completions` expects bash, zsh, fish, or packages", file=sys.stderr)
        return 2
    config, adapters, cache, errors = _build_context(args)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 2
    if not adapters:
        return 0
    prefix = (args.bundle_file or "").strip().lower()
    names: set[str] = set()
    if args.installed:
        for info in _scan_installed(adapters):
            names.add(info.name or info.id)
    else:
        engine = SearchEngine(adapters, cache=cache, ttl=config.cache.ttl_seconds)
        try:
            results = engine.search(prefix) if prefix else []
        except NoSourcesError:
            results = []
        names.update(r.name for r in results)
    ordered = sorted(name for name in names if prefix in name.lower())
    for name in ordered[:50]:
        print(name)
    return 0


# ------------------------------------------------------------- dispatch

_COMMAND_LIST = [
    (
        "search & install",
        [
            ("-s, --search <query>", "search all sources, typo-tolerant, merged and ranked"),
            ("-i, --install <pkg>...", "install one or more packages (confirm + live progress)"),
            ("-r, --remove <pkg>...", "remove one or more installed packages"),
            ("-U, --upgrade <pkg>...", "upgrade one or more installed packages"),
            ("info <pkg>", "detailed view of a package"),
        ],
    ),
    (
        "maintain",
        [
            ("-u, --update", "refresh every source's index, then tool updaters"),
            ("-l, --list", "list installed packages grouped by source"),
            ("-o, --outdated", "show packages with newer versions available"),
            ("doctor", "scan for duplicate installs across sources"),
            ("history [n]", "show recent transactions (default 20)"),
            ("undo", "reverse the last install or remove"),
        ],
    ),
    (
        "share",
        [
            ("export [file]", "write installed packages as a TOML manifest"),
            ("bundle check <file>", "drift report: manifest vs installed packages"),
            ("bundle install <file>", "install packages a manifest is missing"),
            ("completions <shell|packages>", "print a completion script or package names"),
        ],
    ),
    (
        "options",
        [
            ("-y, --yes", "assume yes to all prompts (scripting)"),
            ("--dry-run", "show what would change without changing anything"),
            ("--json", "machine-readable output"),
            ("--source <src>...", "restrict the action to specific sources"),
            ("-q, --quiet", "suppress informational output"),
            ("--no-progress", "run without the live progress bar"),
            ("-h, --help", "show this help"),
            ("-v, --version", "show version"),
        ],
    ),
]


def cmd_help() -> int:
    """Bare `ins`: a good-looking list of every command and option."""
    console = Console()
    console.print(
        f"[bold {theme.ACCENT}]ins — universal CLI package search/install tool for Linux[/]\n"
    )
    for title, rows in _COMMAND_LIST:
        table = Table(
            box=ROUNDED,
            border_style="dim",
            title=f"[{theme.ACCENT}]{title}[/]",
            header_style=f"bold {theme.ACCENT}",
            pad_edge=False,
            collapse_padding=True,
        )
        table.add_column("Command")
        table.add_column("Description", style=theme.DIM)
        for command, description in rows:
            escaped = command.replace("[", "\\[")
            table.add_row(f"[bold]{escaped}[/]", description)
        console.print(table)
    console.print(
        f"[dim]{theme.ARROW} every action needs an explicit flag or subcommand[/]"
    )
    return 0


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
    if args.command == "history":
        chosen.append("history")
    if args.command == "undo":
        chosen.append("undo")
    if args.command == "completions":
        chosen.append("completions")
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
    if args.command == "history":
        return cmd_history(args)
    if args.command == "undo":
        return cmd_undo(args)
    if args.command == "completions":
        return cmd_completions(args)
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
    if args.web or args.page is not None or args.per_page is not None:
        print("error: --web/--page/--per-page require a search (-s QUERY)", file=sys.stderr)
        return 2
    return cmd_help()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return dispatch(args)
    except BrokenPipeError:
        # Consumer (e.g. `ins -l | head`) closed the pipe: exit quietly
        # instead of dumping "Exception ignored while flushing" noise.
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
        except OSError:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
