"""Generate the animated terminal-scene SVGs for the ins README.

Every scene is a self-contained animated SVG (SMIL only, so GitHub renders
them in <img> tags) and loops with a short pause after each run.

Usage:  python3 tools/gen_readme_svgs.py
Output: assets/ins-*.svg
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets")

MONO = "ui-monospace, 'JetBrains Mono', 'DejaVu Sans Mono', Menlo, Consolas, monospace"

CARD = "#0a0d12"
EDGE = "#30363d"
FG = "#e6edf3"
META = "#8b949e"
DIM = "#6e7681"
BLUE = "#58a6ff"
GREEN = "#3fb950"
ORANGE = "#f0883e"
YELLOW = "#d29922"

ADV = 0.6
PAUSE = 3.0
LOOPS = 6


def mono(text: str, x: float, y: float, size: float = 14, fill: str = FG,
         bold: bool = False, fade: float | None = None, anchor: str = "start") -> str:
    fw = ' font-weight="700"' if bold else ""
    if fade is not None:
        anim = (f' opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.35s"'
                f' begin="{fade}" fill="freeze"/></text>')
        return (f'<text xml:space="preserve" x="{x:.1f}" y="{y:.1f}" font-family="{MONO}" font-size="{size}"'
                f' fill="{fill}"{fw} text-anchor="{anchor}">{escape(text)}{anim}')
    return (f'<text xml:space="preserve" x="{x:.1f}" y="{y:.1f}" font-family="{MONO}" font-size="{size}"'
            f' fill="{fill}"{fw} text-anchor="{anchor}">{escape(text)}</text>')


def typed_clip(cid: str, x: float, y: float, width: float, begin: float,
               dur: float = 1.1) -> str:
    return (f'<clipPath id="{cid}"><rect x="{x}" y="{y - 20}" width="{width}" height="24">'
            f'<animate attributeName="width" from="0" to="{width}" dur="{dur}" begin="{begin}" fill="freeze"/>'
            f'</rect></clipPath>')


def cursor(x: float, y: float, begin: float, color: str = GREEN, size: float = 15) -> str:
    return (f'<rect x="{x}" y="{y}" width="8" height="{size}" fill="{color}" opacity="0">'
            f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.08;0.5;0.58"'
            f' dur="1.1s" begin="{begin}" repeatCount="indefinite"/></rect>')


def draw_path(d: str, stroke: str, width: float, begin: float, dur: float = 0.7,
              length: float = 40) -> str:
    return (f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{width}" '
            f'stroke-linecap="round" stroke-linejoin="round" '
            f'stroke-dasharray="{length}" stroke-dashoffset="{length}" opacity="0">'
            f'<animate attributeName="stroke-dashoffset" from="{length}" to="0" dur="{dur}" begin="{begin}" fill="freeze"/>'
            f'<animate attributeName="opacity" from="0" to="1" dur="0.15s" begin="{begin}" fill="freeze"/>'
            f'</path>')


def progress_bar(x: float, y: float, width: float, gid: str, begin: float,
                 dur: float = 1.8) -> str:
    bg = (f'<rect x="{x}" y="{y}" width="{width}" height="8" rx="4" fill="#21262d" opacity="0">'
          f'<animate attributeName="opacity" values="0;1" dur="0.2s" begin="{begin}" fill="freeze"/></rect>')
    fill = (f'<rect x="{x}" y="{y}" width="0" height="8" rx="4" fill="url(#{gid})" opacity="0">'
            f'<animate attributeName="opacity" values="0;1" dur="0.2s" begin="{begin}" fill="freeze"/>'
            f'<animate attributeName="width" from="0" to="{width}" dur="{dur}" begin="{begin}" fill="freeze"/></rect>')
    return bg + fill


def gradient(gid: str, c1: str, c2: str) -> str:
    return (f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient>')


def terminal_frame(x: float, y: float, w: float, h: float, title: str) -> str:
    frame = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{CARD}" stroke="{EDGE}" stroke-width="1.5"/>'
             f'<circle cx="{x + 22}" cy="{y + 20}" r="5.5" fill="#ff5f56"/>'
             f'<circle cx="{x + 42}" cy="{y + 20}" r="5.5" fill="#ffbd2e"/>'
             f'<circle cx="{x + 62}" cy="{y + 20}" r="5.5" fill="#27c93f"/>')
    return frame + mono(title, x + w / 2, y + 25, 12, DIM, anchor="middle")


def svg(w: int, h: int, defs: str, body: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">\n'
            f"<defs>{defs}</defs>\n"
            f"{body}\n</svg>\n")


def loopify(data: str) -> str:
    root = ET.fromstring(data)
    end = 0.0
    for el in root.iter():
        b = el.get("begin")
        if b is None or not re.fullmatch(r"\d+(\.\d+)?", b):
            continue
        d = el.get("dur")
        d = float(d.rstrip("s")) if d else 0.0
        end = max(end, float(b) + d)
    period = end + PAUSE

    def rep(m: re.Match) -> str:
        b = float(m.group(1))
        times = "; ".join(f"{b + i * period:.1f}" for i in range(LOOPS))
        return f'begin="{times}"'

    return re.sub(r'begin="(\d+(?:\.\d+)?)"', rep, data)


def install() -> str:
    W, H = 720, 280
    body = terminal_frame(24, 24, 672, 232, "ins — install")
    lines = [
        ("cmd", "curl -sSL https://raw.githubusercontent.com/savai15/ins/main/install.sh \\", 0.5),
        ("cmd", "  install.sh | bash", 1.6),
        ("cmd", "pipx install git+https://github.com/savai15/ins", 2.6),
        ("cmd", "pip install --user git+https://github.com/savai15/ins", 3.7),
    ]
    y = 76
    for n, (kind, text, begin) in enumerate(lines):
        w = len(text) * ADV * 14
        if kind == "cmd":
            body += mono("$ " if n == 0 else "  ", 24, y, 14, DIM)
            body += f'<g clip-path="url(#in{n})">{mono(text, 40.8, y, 14, FG)}</g>'
            if n == len(lines) - 1:
                body += cursor(40.8 + w + 4, y - 12, begin + 1.2)
        y += 30
    body += mono("optional inline icons: pipx inject ins term-image   ·   man ins",
                 40, 214, 13, DIM, fade=6.0)
    defs = "".join(
        typed_clip(f"in{i}", 40.8, 76 + 30 * i, len(text) * ADV * 14, begin)
        for i, (_, text, begin) in enumerate(lines))
    return loopify(svg(W, H, defs, body))


def demo() -> str:
    W, H = 720, 408
    body = terminal_frame(24, 24, 672, 360, "ins — quick demo")
    body += mono("$ ", 24, 76, 14, DIM)
    body += f'<g clip-path="url(#d0)">{mono("ins -s vcl", 40.8, 76, 14, FG)}</g>'
    body += cursor(40.8 + 10 * ADV * 14 + 4, 64, 1.9)
    body += mono("vlc [apt] 3.0.23-1", 24, 106, 14, GREEN, fade=1.8)
    body += mono("  multimedia player and streamer", 175.2, 106, 14, DIM, fade=1.8)
    body += mono("3 sources searched · 0.9s · 12 results", 24, 136, 14, DIM, fade=2.3)
    body += mono("$ ", 24, 166, 14, DIM)
    body += f'<g clip-path="url(#d1)">{mono("ins -i vlc -y", 40.8, 166, 14, FG)}</g>'
    body += mono("installing vlc [apt] · 35.3 KB", 24, 196, 14, META, fade=3.6)
    body += progress_bar(24, 204, 300, "db", 3.8)
    body += (f'<g transform="translate(24,{226 - 6})">'
             f'{draw_path("M2 0 L6 5 L14 -5", GREEN, 2.4, 5.6, length=20, dur=0.4)}</g>')
    body += mono("installed vlc from apt", 44, 226, 14, GREEN, fade=5.6)
    body += mono("$ ", 24, 256, 14, DIM)
    body += f'<g clip-path="url(#d2)">{mono("ins -u", 40.8, 256, 14, FG)}</g>'
    body += cursor(40.8 + 6 * ADV * 14 + 4, 244, 7.8)
    body += mono("apt: up to date", 24, 286, 14, DIM, fade=7.8)
    body += mono("snap: 2 update(s)   pipx: ran", 24, 316, 14, DIM, fade=8.2)
    body += (f'<g transform="translate(24,{346 - 6})">'
             f'{draw_path("M2 0 L6 5 L14 -5", GREEN, 2.4, 9.0, length=20, dur=0.4)}</g>')
    body += mono("2 packages updated across snap", 44, 346, 14, GREEN, fade=9.0)
    defs = (typed_clip("d0", 40.8, 76, 10 * ADV * 14, 0.5)
            + typed_clip("d1", 40.8, 166, 13 * ADV * 14, 2.9)
            + typed_clip("d2", 40.8, 256, 6 * ADV * 14, 6.6, dur=0.9)
            + gradient("db", BLUE, GREEN))
    return loopify(svg(W, H, defs, body))


def doctor() -> str:
    W, H = 720, 384
    body = terminal_frame(24, 24, 672, 336, "ins — doctor")
    body += mono("$ ", 24, 76, 14, DIM)
    body += f'<g clip-path="url(#dc)">{mono("ins doctor", 40.8, 76, 14, FG)}</g>'
    table = [
        ("Duplicate installations", 2.0, FG, 15, True),
        ("╭──────────┬───────────────────┬──────────────╮", 2.4, DIM, 13, False),
        ("│Package   │Installed via      │Versions      │", 2.7, META, 13, False),
        ("├──────────┼───────────────────┼──────────────┤", 3.0, DIM, 13, False),
        ("│vlc       │[apt] [snap]       │3.0.23-1      │", 3.3, FG, 13, False),
        ("│          │                   │3.0.20        │", 3.6, FG, 13, False),
        ("╰──────────┴───────────────────┴──────────────╯", 3.9, DIM, 13, False),
    ]
    y = 104
    for text, begin, color, size, bold in table:
        body += mono(text, 40, y, size, color, bold=bold, fade=begin)
        y += 24
    body += mono("sources: 2/8 detected (apt, snap)", 40, 274, 13, DIM, fade=4.3)
    body += mono("cache: 4 entries, 0.03 MB (.../ins/cache.db)", 40, 296, 13, DIM, fade=4.6)
    body += mono("config: ~/.config/ins/config.toml", 40, 318, 13, DIM, fade=4.9)
    body += mono("Remove 'vlc' from snap? [y/N]", 40, 342, 14, ORANGE, bold=True, fade=5.3)
    body += cursor(40 + 29 * ADV * 14 + 4, 330, 5.8, color=ORANGE)
    defs = typed_clip("dc", 40.8, 76, 10 * ADV * 14, 0.5)
    return loopify(svg(W, H, defs, body))


def config() -> str:
    W, H = 720, 396
    body = terminal_frame(24, 24, 672, 348, "~/.config/ins/config.toml")
    lines = [
        (0, "# ~/.config/ins/config.toml"),
        (1, "[sources]"),
        (2, "priority", '["apt", "flatpak", "dnf", "pacman", "zypper", "snap", "nix", "apk"]', ""),
        (-1, ""),
        (1, "[cache]"),
        (2, "enabled", "true", ""),
        (2, "ttl_seconds", "3600", ""),
        (2, "max_entries", "5000", ""),
        (-1, ""),
        (1, "[updaters]"),
        (0, "# skip built-in tool updaters: pipx, uv, rustup"),
        (2, "disable", "[]", ""),
        (0, "# opt-in: fwupd can prompt for admin rights"),
        (2, "enable", '["fwupd"]', "  # example: firmware metadata"),
        (0, "# extra update commands run by ins -u (name = argv list)"),
        (2, "custom", '{ texlive = ["tlmgr", "update", "--all"] }', ""),
    ]
    y = 76
    last_y = 76
    for i, line in enumerate(lines):
        kind = line[0]
        begin = 0.8 + i * 0.22
        if kind == -1:
            y += 19
            continue
        last_y = y
        if kind == 0:
            body += mono(line[1], 40, y, 13, DIM, fade=begin)
        elif kind == 1:
            body += mono(line[1], 40, y, 13, ORANGE, bold=True, fade=begin)
        else:
            _, key, val, com = line
            body += mono(key, 40, y, 13, BLUE, fade=begin)
            if val.startswith(('"', "[", "{")):
                body += mono(" = " + val, 40 + len(key) * 7.8, y, 13, GREEN, fade=begin)
            else:
                body += mono(" = " + val, 40 + len(key) * 7.8, y, 13, YELLOW, fade=begin)
            if com:
                body += mono(com, 40 + (len(key) + 3 + len(val)) * 7.8, y, 13, DIM, fade=begin)
        y += 19
    body += cursor(40 + 54 * 7.8 + 8, last_y - 12, 4.6)
    return loopify(svg(W, H, "", body))


def dev() -> str:
    W, H = 720, 280
    body = terminal_frame(24, 24, 672, 232, "ins — development")
    body += mono("$ ", 24, 76, 14, DIM)
    body += f'<g clip-path="url(#v0)">{mono("git clone https://github.com/savai15/ins && cd ins", 40.8, 76, 14, FG)}</g>'
    body += mono("$ ", 24, 112, 14, DIM)
    body += f'<g clip-path="url(#v1)">{mono("pip install -e .[dev]", 40.8, 112, 14, FG)}</g>'
    body += mono("$ ", 24, 148, 14, DIM)
    body += f'<g clip-path="url(#v2)">{mono("pytest -q", 40.8, 148, 14, FG)}</g>'
    body += progress_bar(24, 158, 220, "vb", 3.6, dur=1.4)
    body += mono("270 passed in 2.15s", 258, 164, 14, GREEN, fade=5.2)
    body += mono("$ ", 24, 186, 14, DIM)
    body += f'<g clip-path="url(#v3)">{mono("ruff check .", 40.8, 186, 14, FG)}</g>'
    body += cursor(40.8 + 12 * ADV * 14 + 4, 174, 6.7)
    body += (f'<g transform="translate(24,{216 - 6})">'
             f'{draw_path("M2 0 L6 5 L14 -5", GREEN, 2.4, 7.0, length=22, dur=0.4)}</g>')
    body += mono("all checks passed", 44, 216, 14, GREEN, fade=7.0)
    body += mono("CI: pytest 3.11 · 3.12 · 3.13 + ruff — every push",
                 40, 248, 13, DIM, fade=7.8)
    defs = (typed_clip("v0", 40.8, 76, 50 * ADV * 14, 0.5, dur=1.2)
            + typed_clip("v1", 40.8, 112, 23 * ADV * 14, 1.9)
            + typed_clip("v2", 40.8, 148, 9 * ADV * 14, 2.6, dur=0.9)
            + typed_clip("v3", 40.8, 186, 12 * ADV * 14, 5.6, dur=0.9)
            + gradient("vb", BLUE, GREEN))
    return loopify(svg(W, H, defs, body))


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    panels = {
        "ins-install.svg": install,
        "ins-demo.svg": demo,
        "ins-doctor.svg": doctor,
        "ins-config.svg": config,
        "ins-dev.svg": dev,
    }
    for name, builder in panels.items():
        data = builder()
        path = os.path.join(OUT, name)
        with open(path, "w") as fh:
            fh.write(data)
        print(f"{name:20s} {len(data):6d} bytes")


if __name__ == "__main__":
    main()
