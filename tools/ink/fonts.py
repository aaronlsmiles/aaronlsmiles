"""Geist, the house face, cut down to the glyphs each SVG uses and embedded as a data: URL.

An SVG shown through <img> may load nothing from outside itself, so its font travels inside it. The source is the
studio site's own latin subset (variable, 400 to 800; its `tnum` swaps the digits only), copied into fonts/.
Widths come from the font's own advances at the weight in use, so a line can be wrapped or cut before it is drawn.
Kerning is left out of the measure: it moves a line by a pixel or two, well inside the margins.
"""
from __future__ import annotations

import base64
import functools
import io
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

FONT = Path(__file__).resolve().parents[2] / "fonts/geist-latin.woff2"
FAMILY = "Geist"
FEATURES = ["kern", "liga", "calt", "tnum"]


@functools.lru_cache(maxsize=None)
def _advances(weight: int) -> tuple[dict[int, int], int]:
    """Advance width of every mapped code point at one weight, and the font's units per em."""
    font = instancer.instantiateVariableFont(TTFont(FONT), {"wght": weight})
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    return {cp: hmtx[name][0] for cp, name in cmap.items()}, font["head"].unitsPerEm


def width(text: str, size: float, weight: int = 400, tracking: float = 0.0) -> float:
    """Rendered width in px of `text` at `size` px, with `tracking` in em between letters (as CSS letter-spacing)."""
    adv, upem = _advances(weight)
    missing = adv.get(ord("?"), upem // 2)
    w = sum(adv.get(ord(c), missing) for c in text) * size / upem
    return w + tracking * size * max(len(text) - 1, 0)


def has(text: str) -> bool:
    """True when the font draws every character of `text` (emoji and most scripts beyond latin fall back)."""
    adv, _ = _advances(400)
    return all(ord(c) in adv for c in text)


def face(text: str) -> str:
    """An @font-face rule carrying Geist cut to the characters of `text`, as WOFF2 in a data: URL."""
    font = TTFont(FONT)
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = FEATURES
    opts.name_IDs = [0, 1, 2, 3, 4, 5, 6]  # keep the copyright and licence lines with the glyphs (OFL)
    opts.notdef_outline = True
    s = subset.Subsetter(opts)
    s.populate(text="".join(sorted(set(text + " .,0123456789"))))
    s.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return (f"@font-face{{font-family:'{FAMILY}';src:url(data:font/woff2;base64,{b64}) format('woff2');"
            f"font-weight:400 800;font-style:normal}}")
