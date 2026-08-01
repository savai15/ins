"""Rich rendering: rounded boxes, pastel source tags, accent titles.

The "also via" line lives inside the same table cell as the app name, which
guarantees column alignment without any manual padding.
"""

from __future__ import annotations

from rich.box import ROUNDED
from rich.console import Console
from rich.table import Table

from ins import theme
from ins.search_engine import GroupedResult


def _source_tag(source: str) -> str:
    color = theme.color_for_source(source)
    return f"[{color}]\\[{source}][/]"


def _first_line(text: str | None) -> str:
    text = (text or "").strip()
    return text.splitlines()[0] if text else ""


def _truncate(text: str, width: int = 96) -> str:
    """Cap description length so search rows stay 1-2 lines."""
    if len(text) <= width:
        return text
    return text[: width - 1].rstrip() + "…"


def _table(title: str) -> Table:
    return Table(
        title=f"[{theme.ACCENT}]{title}[/]",
        title_justify="left",
        header_style=f"bold {theme.ACCENT}",
        border_style="dim",
        box=ROUNDED,
        pad_edge=False,
        collapse_padding=True,
    )


def render_search_results(console: Console, query: str, results: list[GroupedResult]) -> None:
    """Print a table of grouped results: Package cell + dim Description cell."""
    table = _table(f"'{query}'")
    table.add_column("Package", min_width=24)
    table.add_column("Description", style=theme.DIM, overflow="fold")

    for group in results:
        package_cell = f"[bold]{group.name}[/bold] {_source_tag(group.primary.source)}"
        if group.primary.version:
            package_cell += f" [dim]{group.primary.version}[/dim]"
        if group.any_installed:
            package_cell += f" [{theme.SUCCESS}]\\[installed][/]"
        lines = [package_cell]
        if group.also_via:
            lines.append(f"[dim]also via: {', '.join(group.also_via)}[/]")
        package_text = "\n".join(lines)

        desc_lines = [_truncate(_first_line(group.primary.description))] if group.primary.description else []
        if group.stale:
            desc_lines.append("[dim](cached result — source offline)[/]")
        desc_text = "\n".join(desc_lines)

        table.add_row(package_text, desc_text)

    console.print(table)


def render_info(
    console: Console,
    group: GroupedResult,
    extras: dict[str, dict[str, str]],
) -> None:
    """Detail view for one app: header + per-source row table."""
    console.print(f"[bold {theme.ACCENT}]{group.name}[/]")
    description = extras.get(group.primary.source, {}).get("description") or group.primary.description
    if description:
        console.print(f"[dim]{_first_line(description)}[/dim]")

    infos = [group.primary, *group.alternatives]

    table = _table("sources")
    table.add_column("Source", min_width=10)
    table.add_column("Version")
    table.add_column("Size", justify="right")
    table.add_column("State")
    table.add_column("License")
    for info in infos:
        extra = extras.get(info.source, {})
        state = f"[{theme.SUCCESS}]installed[/]" if info.installed else "not installed"
        table.add_row(
            _source_tag(info.source),
            info.version or "—",
            info.size_human or "—",
            state,
            extra.get("license") or "—",
        )
    console.print(table)

    homepages = [
        (info.source, extras.get(info.source, {}).get("homepage")) for info in infos
    ]
    homepages = [(source, url) for source, url in homepages if url]
    if homepages:
        console.print(f"[{theme.ACCENT}]homepages[/]")
        for source, url in homepages:
            console.print(f"  {_source_tag(source)} [dim]{url}[/]")


def render_list(console: Console, installed: list) -> None:
    """`ins --list`: installed packages, one row per source install."""
    if not installed:
        console.print(f"[dim]{theme.ARROW} no packages installed[/]")
        return
    table = _table("Installed packages")
    table.add_column("Package", min_width=24)
    table.add_column("Version")
    for info in installed:
        table.add_row(
            f"[bold]{info.name}[/bold] {_source_tag(info.source)}",
            info.version or "—",
        )
    console.print(table)


def render_outdated(console: Console, outdated: list) -> None:
    """`ins --outdated`: installed -> available versions per package."""
    if not outdated:
        console.print(f"[{theme.SUCCESS}]{theme.CHECK} all packages up to date[/]")
        return
    table = _table("Updates available")
    table.add_column("Package")
    table.add_column("Installed")
    table.add_column("Available", min_width=30)
    for info in outdated:
        table.add_row(
            f"[bold]{info.name}[/bold] {_source_tag(info.source)}",
            info.version or "—",
            f"[{theme.ACCENT}]{info.available or '?'}[/]",
        )
    console.print(table)


def render_duplicates(
    console: Console,
    duplicates: list[tuple[str, list]],
) -> None:
    """Doctor report: apps installed via more than one source."""
    if not duplicates:
        console.print(f"[{theme.SUCCESS}]{theme.CHECK} no duplicate installations found[/]")
        return
    table = _table("Duplicate installations")
    table.add_column("Package")
    table.add_column("Installed via")
    table.add_column("Versions", min_width=28)
    for _key, infos in duplicates:
        sources = " ".join(_source_tag(i.source) for i in infos)
        versions = "\n".join(i.version or "?" for i in infos)
        table.add_row(f"[bold]{infos[0].name}[/bold]", sources, versions)
    console.print(table)
