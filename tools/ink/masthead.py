"""The masthead: the studio's name over StillDrawn's question, asked once.

Left, the inked panel. Right, the frame a Runway Gen-4.5 clip made of it, which plays once from frame 4 to frame 120
when the page loads and then holds; a faint copy of the name slips out of register while it plays and settles. Under
reduced motion nothing moves: the two tiles simply sit side by side, the drawing and its last frame.

The frames are the studio site's own (StillDrawn release, CC BY 4.0), cut small by `frames.py` into assets/src/.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from .svg import NARROW, WIDE, Doc, Theme, fonts

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "assets/src/masthead"
NAME, LINE = "Studio Nephele", "From limn to liminal."
T0, STEP = 1.0, 0.6  # the first frame shows at once and holds a second; then a new frame every 0.6 s


def at(i: int) -> float:
    """When clip frame i appears."""
    return 0.0 if i == 0 else T0 + (i - 1) * STEP


def _uri(p: Path) -> str:
    return "data:image/webp;base64," + base64.b64encode(p.read_bytes()).decode("ascii")


def _frames() -> tuple[Path, list[tuple[int, Path]]]:
    meta = json.loads((SRC / "frames.json").read_text())
    return SRC / meta["panel"], [(f["frame"], SRC / f["file"]) for f in meta["clip"]]


def alt() -> str:
    _, clip = _frames()
    return (f"{NAME}. {LINE} An inked panel of a station platform, and frame {clip[-1][0]} of a Runway Gen-4.5 clip "
            "made from it, which plays once from the drawing to that frame.")


def draw(width: int, theme: Theme) -> str:
    panel, clip = _frames()
    wide = width == WIDE
    pad = 40 if wide else 20
    inner = width - 2 * pad
    name_size = 84 if wide else 46
    track = -0.035
    line_size = 30 if wide else 20
    cap, cap2 = (24, 22) if wide else (19, 17)

    # The name, then the line: on one baseline when both fit with room between them, else stacked.
    nw = fonts.width(NAME, name_size, 700, track)
    lw = fonts.width(LINE, line_size, 400)
    y = pad + name_size * 0.84
    one_row = wide and nw + 48 + lw <= inner
    tile_gap = 24 if wide else 16
    top = y + (36 if one_row else line_size + 18 + (34 if wide else 26))
    tw = (inner - tile_gap) / 2 if wide else inner
    th = tw * 9 / 16
    tiles = [(pad, top), (pad + tw + tile_gap, top)] if wide else [(pad, top), (pad, top + th + cap + cap2 + 40)]
    cap_y = lambda ty: ty + th + cap + 12  # noqa: E731
    height = cap_y(tiles[1][1]) + cap2 + 10 + pad

    d = Doc(width, round(height), theme, alt())
    d.css.append(".fr{opacity:0}.fr.end{opacity:1}.ct{opacity:0}.ct.end{opacity:1}.gh{opacity:0}")
    anim = ["@media (prefers-reduced-motion:no-preference){.fr.end,.ct.end{opacity:0}",
            "@keyframes on{to{opacity:1}}@keyframes off{to{opacity:0}}",
            "@keyframes slip{0%{opacity:0;transform:none}12%{opacity:.32}82%{opacity:.32;transform:translate(5px,2px)}"
            "100%{opacity:0;transform:translate(5px,2px)}}",
            f".gh{{animation:slip {at(len(clip) - 1) - T0 + 1.2:.2f}s cubic-bezier(.2,.7,.2,1) {T0 - 0.2:.2f}s forwards}}"]
    for i in range(len(clip)):
        t = at(i)
        anim.append(f".f{i}{{animation:on .01s linear {t:.2f}s forwards}}")
        nxt = f",off .01s linear {at(i + 1):.2f}s forwards" if i < len(clip) - 1 else ""
        anim.append(f".c{i}{{animation:on .01s linear {t:.2f}s forwards{nxt}}}")
    anim.append("}")
    d.css.append("".join(anim))

    # The name, with its ghost under it (the copy that drifts).
    d.add(f'<g class="gh"><text x="{pad}" y="{y:.1f}" font-size="{name_size}" font-weight="700" '
          f'letter-spacing="{track}em" fill="{theme.ink}">{NAME}</text></g>')
    d.words(pad, y, NAME, name_size, 700, tracking=track)
    if one_row:
        d.words(width - pad, y, LINE, line_size, 400, anchor="end")
    else:
        d.words(pad, y + line_size + 18, LINE, line_size, 400)

    # The tiles: the drawing, then the clip's frames stacked so each new one covers the last.
    (lx, ly), (rx, ry) = tiles
    clipattr = 'preserveAspectRatio="xMidYMid slice"'
    d.add(f'<rect x="{lx}" y="{ly:.1f}" width="{tw:.1f}" height="{th:.1f}" fill="{theme.raised}"/>')
    d.add(f'<image x="{lx}" y="{ly:.1f}" width="{tw:.1f}" height="{th:.1f}" {clipattr} href="{_uri(panel)}"/>')
    d.add(f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{tw:.1f}" height="{th:.1f}" fill="{theme.raised}"/>')
    for i, (_, p) in enumerate(clip):
        end = " end" if i == len(clip) - 1 else ""
        d.add(f'<image class="fr f{i}{end}" x="{rx:.1f}" y="{ry:.1f}" width="{tw:.1f}" height="{th:.1f}" '
              f'{clipattr} href="{_uri(p)}"/>')

    # Captions: what each tile is, and which frame is showing.
    d.words(lx, cap_y(ly), "The drawing", cap, 600)
    d.words(lx, cap_y(ly) + cap2 + 8, "An inked panel from StillDrawn", cap2, 400, fill=theme.muted)
    for i, (n, _) in enumerate(clip):
        end = " end" if i == len(clip) - 1 else ""
        d.words(rx, cap_y(ry), f"Frame {n}", cap, 600, cls=f"ct c{i}{end}")
    d.words(rx, cap_y(ry) + cap2 + 8, "of a Runway Gen-4.5 clip made from it", cap2, 400, fill=theme.muted)
    return d.render()
