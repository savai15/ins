"""Rich rendering of search results (Part 6).

The "also via" line lives inside the same table cell as the app name, which
guarantees column alignment without any manual padding.
"""

from __future__ import annotations

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


def render_search_results(console: Console, query: str, results: list[GroupedResult]) -> None:
    """Print a table of grouped results: Package cell + dim Description cell."""
    table = Table(
        title=f"'{query}'",
        title_justify="left",
        header_style="bold",
        box=None,
        pad_edge=False,
        collapse_padding=True,
    )
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

        desc_lines = [_first_line(group.primary.description)] if group.primary.description else []
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
    console.print(f"[bold]{group.name}[/bold]")
    description = extras.get(group.primary.source, {}).get("description") or group.primary.description
    if description:
        console.print(f"[dim]{_first_line(description)}[/dim]")

    table = Table(box=None, header_style="bold", pad_edge=False, collapse_padding=True)
    table.add_column("Source", min_width=10)
    table.add_column("Version")
    table.add_column("Size", justify="right")
    table.add_column("State")
    table.add_column("License")
    table.add_column("Homepage", overflow="fold")

    infos = [group.primary, *group.alternatives]
    for info in infos:
        extra = extras.get(info.source, {})
        state = f"[{theme.SUCCESS}]installed[/]" if info.installed else "not installed"
        table.add_row(
            _source_tag(info.source),
            info.version or "—",
            info.size_human or "—",
            state,
            extra.get("license") or "—",
            extra.get("homepage") or "—",
        )
    console.print(table)


def render_duplicates(
    console: Console,
    duplicates: list[tuple[str, list]],
) -> None:
    """Doctor report: apps installed via more than one source."""
    if not duplicates:
        console.print(f"[{theme.SUCCESS}]no duplicate installations found[/]")
        return
    table = Table(
        title="Duplicate installations",
        title_justify="left",
        box=None,
        header_style="bold",
        pad_edge=False,
        collapse_padding=True,
    )
    table.add_column("Package")
    table.add_column("Installed via")
    table.add_column("Versions")
    for _key, infos in duplicates:
        sources = " ".join(_source_tag(i.source) for i in infos)
        versions = ", ".join(i.version or "?" for i in infos)
        table.add_row(f"[bold]{infos[0].name}[/bold]", sources, versions)
    console.print(table)
