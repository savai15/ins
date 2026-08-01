"""Generate the handcrafted animated SVG panels for the ins README.

Every panel is a self-contained animated scene: SMIL + CSS animations only,
so GitHub renders them in <img> tags. Display typography is converted to
vector paths (fonttools) so it looks identical on every OS; body text uses a
safe monospace stack.

Usage:  python3 tools/gen_readme_svgs.py
Output: assets/*.svg
"""

from __future__ import annotations

import os
from xml.sax.saxutils import escape

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets")
FONTS = "/tmp/opencode/fonts"

MONO = "ui-monospace, 'JetBrains Mono', 'DejaVu Sans Mono', Menlo, Consolas, monospace"

# palette (GitHub dark, brand accent)
BG = "#0d1117"
CARD = "#161b22"
EDGE = "#30363d"
FG = "#e6edf3"
META = "#8b949e"
DIM = "#6e7681"
BLUE = "#58a6ff"
GREEN = "#3fb950"
ORANGE = "#f0883e"
PURPLE = "#bc8cff"
YELLOW = "#d29922"
RED = "#f85149"

SRC = {"apt": "#e95420", "dnf": "#51a2da", "pacman": "#1793d1", "zypper": "#73ba25",
       "flatpak": "#4a90d9", "snap": "#82bea0", "nix": "#7eb6a7", "apk": "#0d597f"}


# ------------------------------------------------------------------- fonts

def load_font(path: str, weight: int | None = None):
    font = TTFont(path)
    upem = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    if weight is not None:
        try:
            gs = font.getGlyphSet(location={"wght": weight})
        except Exception:
            gs = font.getGlyphSet()
    else:
        gs = font.getGlyphSet()
    hmtx = font["hmtx"]

    def measure(text: str, size: float) -> float:
        total = 0.0
        for c in text:
            o = ord(c)
            if o not in cmap:
                continue
            total += hmtx[gs[cmap[o]].name][0] * size / upem
        return total

    def paths(text: str, size: float) -> tuple[list[tuple[float, str]], float]:
        k = size / upem
        items: list[tuple[float, str]] = []
        x = 0.0
        for c in text:
            o = ord(c)
            if o not in cmap:
                x += hmtx[".notdef"][0] * k
                continue
            gname = cmap[o]
            pen = SVGPathPen(gs)
            gs[gname].draw(pen)
            d = pen.getCommands()
            if d:
                items.append((x, d))
            x += hmtx[gname][0] * k
        return items, x

    return measure, paths


SPACE_GROTESK = load_font(os.path.join(FONTS, "SpaceGrotesk.ttf"), 700)
MONO_FONT = load_font(os.path.join(FONTS, "JetBrainsMono.ttf"), 500)


def path_text(text: str, x: float, y: float, size: float, fill: str,
              font=SPACE_GROTESK, opacity: str = "", extra: str = "") -> str:
    items, _w = font[1](text, size)
    paths = "".join(
        f'<path transform="translate({x + dx},{y}) scale(1,-1)" d="{d}" fill="{fill}"/>'
        for dx, d in items
    )
    attr = f' opacity="{opacity}"' if opacity else ""
    return f'<g{attr}>{paths}</g>'


def mono(text: str, x: float, y: float, size: float, fill: str = FG, bold: bool = False,
         anchor: str = "start", cls: str = "", delay: float | None = None) -> str:
    cls = f' class="{cls}"' if cls else ""
    fw = ' font-weight="700"' if bold else ""
    style = f' style="animation-delay:{delay}s"' if delay is not None else ""
    return (f'<text xml:space="preserve" x="{x:.1f}" y="{y:.1f}" font-family="{MONO}" font-size="{size}"'
            f' fill="{fill}"{fw}{cls}{style} text-anchor="{anchor}">{escape(text)}</text>')


def wrap(text: str, size: float, width: float) -> list[str]:
    chars = int(width / (0.6 * size))
    out, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > chars:
            out.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        out.append(cur)
    return out


def hline(x1: float, y: float, x2: float, stroke: str = EDGE) -> str:
    return f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{stroke}" stroke-width="1"/>'


def card(w: int, h: int) -> str:
    return f'<rect x="8" y="8" width="{w - 16}" height="{h - 16}" rx="16" fill="{BG}" stroke="{EDGE}" stroke-width="1.5"/>'


def panel_header(index: str, title: str, accent: str) -> str:
    idx = mono(f"{index} /", 24, 40, 14, DIM)
    tw = SPACE_GROTESK[0](title, 28)
    title_p = path_text(title, 24 + 60, 40, 28, accent)
    line = (f'<rect x="24" y="48" width="{tw + 6:.0f}" height="3" rx="1.5" fill="{accent}" opacity="0">'
            f'<animate attributeName="opacity" values="0;1" dur="0.4s" begin="0.9s" fill="freeze"/></rect>')
    return idx + title_p + line


def typed_clip(cid: str, x: float, y: float, width: float, begin: float, dur: float = 1.1) -> str:
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


def fade_grp(begin: float, dur: float = 0.35, cls: str = "") -> tuple[str, str]:
    gid = f"f{begin:.2f}".replace(".", "")
    return (f'<g class="fade fade-{gid}" id="{gid}">', f'</g>')

# ------------------------------------------------------------------- panels


def tagline() -> str:
    text = "one command to find, install, remove — on linux"
    size = 30
    tw = SPACE_GROTESK[0](text, size)
    x0 = (720 - tw) / 2
    style = """
    @keyframes rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    .wrap { animation: rise .8s ease-out forwards; }
    """
    body = f'<g class="wrap" clip-path="url(#tgclip)">{path_text(text, x0, 78, size, "url(#tg)")}</g>'
    body += cursor(x0 + tw + 6, 64, 3.2)
    defs = f"""
    <linearGradient id="tg" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{BLUE}"><animate attributeName="stop-color" values="{BLUE};{GREEN};{BLUE}" dur="7s" repeatCount="indefinite"/></stop>
      <stop offset="1" stop-color="{GREEN}"><animate attributeName="stop-color" values="{GREEN};{BLUE};{GREEN}" dur="7s" repeatCount="indefinite"/></stop>
    </linearGradient>
    <clipPath id="tgclip"><rect x="{x0}" y="46" width="0" height="52">
      <animate attributeName="width" from="0" to="{tw}" dur="2.6s" begin="0.4s" fill="freeze"/>
    </rect></clipPath>"""
    return svg(720, 140, defs, style, body)


def features() -> str:
    FEATURES = [
        ("8 managers, 1 interface", "apt dnf pacman zypper flatpak snap", "nix apk — merged & ranked", BLUE),
        ("Typo-tolerant search", "\"vcl\" still finds vlc — transposition", "boost vs your real package lists", GREEN),
        ("Safe by default", "pkexec · sudo fallback · confirm with", "sizes · --dry-run previews · -y", ORANGE),
        ("doctor protects you", "duplicate detection that understands", "snap-transition stubs — never your app", RED),
        ("Full lifecycle", "install · remove · update · list · outdated", "· upgrade · info · history · undo", BLUE),
        ("Tool updaters", "pipx · uv · rustup by default, fwupd", "and custom commands opt-in", PURPLE),
        ("Scripting-friendly", "--json · -q · --no-progress · shell", "completions · man page", YELLOW),
        ("Offline cache", "local SQLite with TTL — stale results", "are marked, never fatal", GREEN),
        ("Pretty", "rounded tables · pastel source tags ·", "live progress · erase animation", PURPLE),
    ]
    W, H = 720, 432
    cw, ch, gap = 224, 116, 12
    style = """
    @keyframes rise { from { opacity: 0; transform: translateY(26px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .35; } }
    .card { animation: rise .55s ease-out forwards; }
    .dot { animation: pulse 2.2s ease-in-out infinite; }
    """
    body = panel_header("01", "features", BLUE)
    for i, (title, d1, d2, color) in enumerate(FEATURES):
        cx = 8 + (i % 3) * (cw + gap)
        cy = 64 + (i // 3) * (ch + gap)
        delay = 0.8 + i * 0.13
        body += (f'<g class="card" style="animation-delay:{delay}s">'
                 f'<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" rx="12" fill="{CARD}" stroke="{EDGE}" stroke-width="1.2"/>'
                 f'<circle class="dot" cx="{cx + 16}" cy="{cy + 24}" r="4" fill="{color}"/>'
                 f'{mono(title, cx + 30, cy + 28, 14, FG, bold=True)}'
                 f'{mono(d1, cx + 14, cy + 52, 12.5, META)}'
                 f'{mono(d2, cx + 14, cy + 70, 12.5, META)}'
                 f'<rect x="{cx + 14}" y="{cy + ch - 14}" width="{cw - 28}" height="3" rx="1.5" fill="{color}" opacity="0">'
                 f'<animate attributeName="opacity" values="0;1" dur="0.4s" begin="{delay + 0.5}" fill="freeze"/></rect>'
                 f'</g>')
    return svg(W, H, "", style, body)


def install() -> str:
    W, H = 720, 300
    cmds = [
        ['curl -sSL https://raw.githubusercontent.com/savai15/ins/main/install.sh \\',
         '  install.sh | bash'],
        ['pipx install git+https://github.com/savai15/ins'],
        ['pip install --user git+https://github.com/savai15/ins'],
    ]
    style = """
    @keyframes drop { 0% { transform: translateY(-70px); } 60% { transform: translateY(6px); } 80% { transform: translateY(-2px); } 100% { transform: translateY(0); } }
    @keyframes fadein { from { opacity: 0; } to { opacity: 1; } }
    .box { animation: drop .9s cubic-bezier(.2,.8,.3,1) .2s both; }
    .note { opacity: 0; animation: fadein .5s ease-out 6.8s forwards; }
    """
    defs = ""
    body = panel_header("02", "install", GREEN)
    _bw = SPACE_GROTESK[0]("ins", 28)
    box_x = 24 + (58 - _bw) / 2
    body += (f'<g class="box"><rect x="24" y="70" width="58" height="58" rx="12" fill="url(#ig)" stroke="{EDGE}" stroke-width="1.2"/>'
             f'<g><animateTransform attributeName="transform" type="rotate" values="-8;8;-8" dur="3s" begin="2s" repeatCount="indefinite"/>'
             f'{path_text("ins", box_x, 70 + 45, 28, BG)}</g></g>')
    defs = ('<linearGradient id="ig" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="{BLUE}"/><stop offset="1" stop-color="{GREEN}"/></linearGradient>')
    body += mono("Requires Python 3.11+ — any of these three:", 100, 96, 14, META)
    y = 130
    for ci, lines in enumerate(cmds):
        wlast = len(lines[-1]) * 0.6 * 14
        for li, text in enumerate(lines):
            begin = 1.1 + ci * 1.3 + li * 0.9
            w = len(text) * 0.6 * 14
            defs += typed_clip(f"i{ci}{li}", 116.8, y, w, begin)
            body += mono("$ " if li == 0 else "  ", 100, y, 14, DIM)
            body += f'<g clip-path="url(#i{ci}{li})">{mono(text, 116.8, y, 14, FG)}</g>'
            if li == len(lines) - 1:
                body += cursor(116.8 + wlast + 4, y - 12, begin + 1.2)
            y += 34
    body += ('<text class="note" xml:space="preserve" x="100" y="274" font-family="%s" font-size="13" fill="%s">'
             'optional inline icons: pipx inject ins term-image   ·   man ins</text>' % (MONO, DIM))
    return svg(W, H, defs, style, body)


def quickstart() -> str:
    W, H = 720, 420
    style = """
    @keyframes fadein { from { opacity: 0; } to { opacity: 1; } }
    .fade { opacity: 0; animation: fadein .35s ease-out forwards; }
    """
    defs = ""
    body = panel_header("03", "quick start", ORANGE)
    ty = 62
    body += f'<rect x="24" y="{ty}" width="672" height="330" rx="12" fill="#0a0d12" stroke="{EDGE}" stroke-width="1.2"/>'
    dots = "".join(
        f'<circle cx="{x}" cy="{ty + 16}" r="4.5" fill="{c}"/>' for x, c in
        [(38, "#ff5f56"), (56, "#ffbd2e"), (74, "#27c93f")])
    body += dots + mono("ins — demo", 360, ty + 20, 12, DIM, anchor="middle")
    lines = []
    # scene 1: search
    lines.append(("cmd", "ins -s vcl", 0.5, 1.1))
    lines.append(("out", "vlc [apt] 3.0.23-1", 1.8, GREEN))
    lines.append(("dim", "3 sources searched · 0.9s · 12 results", 2.3))
    # scene 2: install
    lines.append(("cmd", "ins -i vlc -y", 2.9, 1.1))
    lines.append(("bar", "installing vlc [apt] · 35.3 KB", 3.6, 3.8))
    lines.append(("ok", "✓ installed vlc from apt", 5.6, GREEN))
    # scene 3: update
    lines.append(("cmd", "ins -u", 6.6, 0.9))
    lines.append(("dim", "apt: up to date", 7.8))
    lines.append(("dim", "snap: 2 update(s)   pipx: ran", 8.2))
    lines.append(("ok", "✓ 2 packages updated across snap", 9.0, GREEN))
    y = ty + 52
    for item in lines:
        kind = item[0]
        if kind == "cmd":
            _, text, begin, dur = item
            w = len(text) * 0.6 * 14
            defs += typed_clip(f"q{int(begin*10)}", 40.8, y, w, begin, dur)
            body += mono("$ ", 24, y, 14, DIM)
            body += f'<g clip-path="url(#q{int(begin*10)})">{mono(text, 40.8, y, 14, FG)}</g>'
            body += cursor(40.8 + w + 4, y - 12, begin + dur + 0.3)
        elif kind == "out":
            _, text, begin, color = item
            body += mono(text, 24, y, 14, color, cls="fade", delay=begin)
            body += mono("  multimedia player and streamer", 24 + 0.6 * 14 * len(text), y, 14, DIM, cls="fade", delay=begin)
        elif kind == "dim":
            _, text, begin = item
            body += mono(text, 24, y, 14, DIM, cls="fade", delay=begin)
        elif kind == "bar":
            _, text, begin, beginfill = item
            body += mono(text, 24, y, 14, META, cls="fade", delay=begin)
            body += (f'<rect x="24" y="{y + 8}" width="300" height="8" rx="4" fill="#21262d" opacity="0">'
                     f'<animate attributeName="opacity" values="0;1" dur="0.2s" begin="{beginfill}" fill="freeze"/></rect>')
            body += (f'<rect x="24" y="{y + 8}" width="0" height="8" rx="4" fill="url(#qb)" opacity="0">'
                     f'<animate attributeName="opacity" values="0;1" dur="0.2s" begin="{beginfill}" fill="freeze"/>'
                     f'<animate attributeName="width" from="0" to="300" dur="1.8s" begin="{beginfill}" fill="freeze"/></rect>')
        elif kind == "ok":
            _, text, begin, color = item
            body += (f'<g transform="translate(24,{y - 6})">'
                     f'{draw_path("M2 0 L6 5 L14 -5", color, 2.4, begin, length=20, dur=0.4)}</g>')
            body += mono(text, 44, y, 14, color, cls="fade", delay=begin)
        y += 30
    defs += ('<linearGradient id="qb" x1="0" y1="0" x2="1" y2="0">'
             f'<stop offset="0" stop-color="{BLUE}"/><stop offset="1" stop-color="{GREEN}"/></linearGradient>')
    return svg(W, H, defs, style, body)


def commands() -> str:
    W, H = 720, 460
    ROWS = [
        ("ins -s <query>", "search all sources — ranked, typo-tolerant"),
        ("ins -i <pkg>...", "install with confirmation + live progress"),
        ("ins -r <pkg>...", "remove installed packages"),
        ("ins -u", "update every source index + tool updaters"),
        ("ins -l", "list installed packages grouped by source"),
        ("ins -o", "packages with newer versions available"),
        ("ins -U <pkg>...", "upgrade installed packages"),
        ("ins info <pkg>", "license · homepage · size per source"),
        ("ins doctor", "duplicate installs · snap-stub aware"),
        ("ins history · undo", "review and reverse recent transactions"),
        ("ins export · bundle", "declarative provisioning manifests"),
        ("--dry-run · --json · -q", "preview · script · quiet"),
    ]
    style = """
    @keyframes fadein { from { opacity: 0; transform: translateX(-8px); } to { opacity: 1; transform: translateX(0); } }
    .row { opacity: 0; animation: fadein .45s ease-out forwards; }
    """
    body = panel_header("04", "commands", BLUE)
    y = 66
    for i, (cmd, desc) in enumerate(ROWS):
        begin = 0.8 + i * 0.18
        h = 28
        body += (f'<g class="row" style="animation-delay:{begin}s">'
                 f'<rect x="24" y="{y}" width="0" height="{h}" fill="{BLUE}" opacity="0.10">'
                 f'<animate attributeName="width" from="0" to="672" dur="0.5s" begin="{begin}" fill="freeze"/></rect>'
                 f'{mono(f"{i + 1:02d}", 30, y + 20, 12, DIM)}'
                 f'{mono(cmd, 66, y + 20, 14, FG, bold=True)}'
                 f'{mono(desc, 340, y + 20, 13, META)}'
                 f'</g>')
        body += hline(24, y + 27, 696, EDGE)
        y += h
    return svg(W, H, "", style, body)


def sources_table() -> str:
    W, H = 720, 380
    COLS = ["search", "install / remove", "update", "upgrade"]
    ROWS = [
        ("apt", "apt-cache search", "apt-get install", "apt-get update", "apt-get upgrade"),
        ("flatpak", "flatpak search", "flatpak install", "flatpak update", "flatpak update"),
        ("dnf", "dnf search -q", "dnf install -y", "dnf upgrade", "dnf upgrade"),
        ("pacman", "pacman -Ss", "pacman -S", "pacman -Sy", "pacman -S"),
        ("zypper", "zypper -q search", "zypper -n install", "zypper -n refresh", "zypper -n update"),
        ("snap", "snap find", "snap install", "snap refresh", "snap refresh"),
        ("nix", "nix search nixpkgs", "nix-env -iA", "nix-channel --update", "nix-env -u"),
        ("apk", "apk search -d", "apk add", "apk update", "apk add -u"),
    ]
    style = """
    @keyframes fadein { from { opacity: 0; } to { opacity: 1; } }
    .row { opacity: 0; animation: fadein .4s ease-out forwards; }
    """
    body = panel_header("05", "supported sources", GREEN)
    xs = [24, 130, 300, 430, 560]
    body += "".join(mono(c.upper(), x, 60, 12, DIM) for c, x in zip(["source", *COLS], xs))
    body += hline(24, 68, 696)
    y = 88
    for i, row in enumerate(ROWS):
        name, *cells = row
        delay = 0.9 + i * 0.16
        body += f'<g class="row" style="animation-delay:{delay}s">'
        body += (f'<circle cx="{xs[0] + 8}" cy="{y - 4}" r="4" fill="{SRC[name]}">'
                 f'<animate attributeName="r" values="4;5.5;4" dur="1.8s" begin="{delay}" repeatCount="indefinite"/></circle>')
        body += mono(name, xs[0] + 20, y, 14, FG, bold=True)
        body += "".join(mono(c, x, y, 13, META) for c, x in zip(cells, xs[1:]))
        body += hline(24, y + 12, 696)
        body += "</g>"
        y += 34
    return svg(W, H, "", style, body)


def config() -> str:
    W, H = 720, 400
    LINES = [
        (0, "# ~/.config/ins/config.toml"),
        (1, "[sources]"),
        (1, 'priority = ["apt", "flatpak", "dnf", "pacman", "zypper", "snap", "nix", "apk"]'),
        (2, ""),
        (1, "[cache]"),
        (1, "enabled = true"),
        (1, "ttl_seconds = 3600"),
        (2, ""),
        (1, "[updaters]"),
        (1, "disable = []"),
        (1, 'enable = ["fwupd"]  # opt-in: may prompt for admin rights'),
        (1, 'custom = { texlive = ["tlmgr", "update", "--all"] }'),
    ]
    style = """
    @keyframes shimmer { 0% { transform: translateX(-1400px); } 100% { transform: translateX(1400px); } }
    @keyframes fadein { from { opacity: 0; } to { opacity: 1; } }
    .fade { opacity: 0; animation: fadein .4s ease-out forwards; }
    .shine { opacity: 0; animation: shimmer 2.4s ease-in-out 4.6s forwards; }
    """
    body = panel_header("06", "configuration", PURPLE)
    body += f'<rect x="24" y="64" width="672" height="308" rx="12" fill="#0a0d12" stroke="{EDGE}" stroke-width="1.2"/>'
    y = 92
    last_y = 92
    for i, (kind, line) in enumerate(LINES):
        if not line:
            y += 22
            continue
        last_y = y
        begin = 0.9 + i * 0.3
        w = len(line) * 0.6 * 13
        if kind == 0:
            body += mono(line, 40, y, 13, DIM)
        elif kind == 1:
            if line.startswith("["):
                body += mono(line, 40, y, 13, ORANGE, bold=True)
            else:
                key, _, rest = line.partition(" = ")
                body += mono(key, 40, y, 13, BLUE)
                if rest:
                    val = rest.split("  # ")[0]
                    com = "  # " + rest.split("  # ")[1] if "  # " in rest else ""
                    if val.startswith(('"', "{")):
                        body += mono(" = " + val, 40 + len(key) * 7.8, y, 13, GREEN)
                    else:
                        body += mono(" = " + val, 40 + len(key) * 7.8, y, 13, YELLOW)
                    if com:
                        body += mono(com, 40 + len(line.replace(com, "")) * 7.8, y, 13, DIM)
        elif kind == 2:
            pass
        y += 22
    body += ('<g class="shine"><rect x="24" y="64" width="260" height="308" fill="url(#sh)" opacity="0.35"/>'
             '<animate attributeName="opacity" values="0;0.5;0" dur="2.4s" begin="4.6s" fill="freeze"/></g>')
    body += cursor(40 + 54 * 7.8 + 8, last_y - 12, 8.0)
    defs = ('<linearGradient id="sh" x1="0" y1="0" x2="1" y2="0">'
            '<stop offset="0" stop-color="#ffffff" stop-opacity="0"/>'
            '<stop offset="0.5" stop-color="#ffffff" stop-opacity="0.6"/>'
            '<stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>')
    return svg(W, H, defs, style, body)


def dev() -> str:
    W, H = 720, 250
    style = """
    @keyframes fadein { from { opacity: 0; } to { opacity: 1; } }
    .fade { opacity: 0; animation: fadein .35s ease-out forwards; }
    """
    defs = ""
    body = panel_header("07", "development", YELLOW)
    steps = [
        ('pip install -e ".[dev]"', 1.0, 1.1),
        ("pytest -q", 2.6, 1.0),
        ("ruff check .", 4.2, 1.0),
    ]
    y = 66
    for i, (cmd, begin, dur) in enumerate(steps):
        w = len(cmd) * 0.6 * 14
        defs += typed_clip(f"d{int(begin)}", 40.8, y, w, begin, dur)
        body += mono("$ ", 24, y, 14, DIM)
        body += f'<g clip-path="url(#d{int(begin)})">{mono(cmd, 40.8, y, 14, FG)}</g>'
        body += cursor(40.8 + w + 4, y - 12, begin + dur + 0.2)
        if i == 1:
            body += (f'<rect x="24" y="{y + 10}" width="220" height="8" rx="4" fill="#21262d" opacity="0">'
                     f'<animate attributeName="opacity" values="0;1" dur="0.2s" begin="{begin + dur + 0.3}" fill="freeze"/></rect>')
            body += (f'<rect x="24" y="{y + 10}" width="0" height="8" rx="4" fill="url(#db)" opacity="0">'
                     f'<animate attributeName="opacity" values="0;1" dur="0.2s" begin="{begin + dur + 0.3}" fill="freeze"/>'
                     f'<animate attributeName="width" from="0" to="220" dur="1.6s" begin="{begin + dur + 0.5}" fill="freeze"/></rect>')
            body += mono("270 passed in 2.15s", 258, y, 14, GREEN, cls="fade", delay=begin + dur + 2.2)
        if i == 2:
            body += (f'<g transform="translate(24,{y - 6})">'
                     f'{draw_path("M2 0 L6 5 L14 -5", GREEN, 2.4, begin + dur + 0.4, length=22, dur=0.4)}</g>')
            body += mono("all checks passed", 56, y, 14, GREEN, cls="fade", delay=begin + dur + 0.5)
        y += 44
    defs += ('<linearGradient id="db" x1="0" y1="0" x2="1" y2="0">'
             f'<stop offset="0" stop-color="{BLUE}"/><stop offset="1" stop-color="{GREEN}"/></linearGradient>')
    body += mono("CI: pytest 3.11 · 3.12 · 3.13 + ruff — every push", 24, y + 8, 13, DIM, cls="fade", delay=6.5)
    return svg(W, H, defs, style, body)


def activity() -> str:
    W, H = 720, 300
    style = """
    @keyframes fadein { from { opacity: 0; } to { opacity: 1; } }
    @keyframes rise { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes wave { 0% { transform: translateX(-80px); opacity: 0; } 12% { opacity: 1; } 88% { opacity: 1; } 100% { transform: translateX(720px); opacity: 0; } }
    .fade { opacity: 0; animation: fadein .5s ease-out forwards; }
    .chip { opacity: 0; animation: rise .5s ease-out forwards; }
    .sweep { animation: wave 3.4s ease-in-out 3s infinite; }
    """
    RAMP = [("#7c2a2a", 0.35), ("#7c2a2a", 1.0), ("#c93636", 1.0), ("#f85149", 1.0)]
    import random
    rng = random.Random(7)
    grid: list[tuple[int, int, int]] = []
    for col in range(48):
        for row in range(7):
            level = rng.random()
            if level > 0.82:
                lvl = 3
            elif level > 0.62:
                lvl = 2
            elif level > 0.45:
                lvl = 1
            elif level > 0.34:
                lvl = 0
            else:
                continue
            grid.append((col, row, lvl))
    x0, y0, step = 40, 104, 11
    cells = ""
    for (col, row, lvl) in grid:
        fill, op = RAMP[lvl]
        begin = 2.4 + col * 0.05
        cells += (f'<rect x="{x0 + col * step}" y="{y0 + row * step}" width="9" height="9" rx="2" '
                  f'fill="{fill}" opacity="0">'
                  f'<animate attributeName="opacity" from="0" to="{op}" dur="0.3s" begin="{begin:.2f}" fill="freeze"/></rect>')
    body = panel_header("08", "activity", RED)
    body += (f'<g class="fade" style="animation-delay:1.6s">'
             f'<rect x="24" y="64" width="672" height="196" rx="14" fill="#0a0d12" stroke="#4f1d1d" stroke-width="1.5"/></g>')
    body += mono("commit activity · last 48 weeks", 40, 88, 13, META, cls="fade", delay=1.9)
    body += mono("release v0.3.0 · 270 tests · MIT", 448, 88, 12.5, DIM, cls="fade", delay=2.1)
    body += cells
    body += (f'<g clip-path="url(#gclip)"><g class="sweep">'
             f'<rect x="0" y="{y0 - 4}" width="70" height="{6 * step + 9 + 8}" fill="url(#gs)" opacity="0.5"/>'
             f'</g></g>')
    body += mono("handcrafted, like everything here", 360, 222, 12, DIM, anchor="middle", cls="fade", delay=5.0)
    body += mono("no stats servers · nothing to break", 360, 238, 12, DIM, anchor="middle", cls="fade", delay=5.2)
    defs = (f'<clipPath id="gclip"><rect x="{x0}" y="{y0}" width="{47 * step + 9}" height="{6 * step + 9}"/></clipPath>'
            '<linearGradient id="gs" x1="0" y1="0" x2="1" y2="0">'
            '<stop offset="0" stop-color="#ff7b72" stop-opacity="0"/>'
            '<stop offset="0.5" stop-color="#f85149" stop-opacity="0.6"/>'
            '<stop offset="1" stop-color="#ff7b72" stop-opacity="0"/></linearGradient>')
    return svg(W, H, defs, style, body)


def footer() -> str:
    W, H = 720, 150
    style = """
    @keyframes fadein { from { opacity: 0; } to { opacity: 1; } }
    @keyframes glow { 0%,100% { opacity: .18; } 50% { opacity: .4; } }
    .glow { animation: glow 3.5s ease-in-out infinite; }
    .fade { opacity: 0; animation: fadein 1.2s ease-out 1.2s forwards; }
    """
    tw = SPACE_GROTESK[0]("ins", 64)
    x0 = (720 - tw) / 2
    body = f'<g class="glow">{path_text("ins", x0, 70, 64, BLUE)}</g>'
    body += path_text("ins", x0, 70, 64, "url(#ft)")
    body += mono("MIT License · © 2026 Savai", 360, 108, 13, META, anchor="middle", cls="fade")
    defs = (f'<linearGradient id="ft" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0" stop-color="{BLUE}"/><stop offset="1" stop-color="{GREEN}"/></linearGradient>')
    return svg(W, H, defs, style, body)


def svg(w: int, h: int, defs: str, style: str, body: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">\n'
            f"<defs>{defs}</defs>\n"
            f"<style>{style}</style>\n"
            f"{body}\n</svg>\n")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    panels = {
        "ins-tagline.svg": tagline,
        "ins-features.svg": features,
        "ins-install.svg": install,
        "ins-quickstart.svg": quickstart,
        "ins-commands.svg": commands,
        "ins-sources-table.svg": sources_table,
        "ins-config.svg": config,
        "ins-dev.svg": dev,
        "ins-activity.svg": activity,
        "ins-footer.svg": footer,
    }
    for name, builder in panels.items():
        data = builder()
        path = os.path.join(OUT, name)
        with open(path, "w") as fh:
            fh.write(data)
        print(f"{name:24s} {len(data):6d} bytes")


if __name__ == "__main__":
    main()
