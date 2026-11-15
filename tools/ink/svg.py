"""The drawing kit every panel shares: the studio's colours, escaping, wrapping and the document wrapper.

Colours are the site's own tokens (studionephele.com src/styles/tokens.css): paper, ink and one gold. Each panel is
drawn twice, once per theme, and <picture> chooses; nothing inside an SVG asks which theme the page is in, because
Safari doesn't answer that question for an image.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from xml.sax.saxutils import escape

from . import fonts

# The two widths every panel is drawn at. A wide panel shows above 600 px, where the README column is 570 to about
# 850 px; a narrow one below, where it is 328 to 570 px. MIN_TEXT is the smallest type each may carry so that no
# word is ever shown under 13 px (house rule): 13 / (570 / 960) and 13 / (310 / 400), with room for a phone README column as narrow as 310 px.
WIDE, NARROW = 960, 400
MIN_TEXT = {WIDE: 22.0, NARROW: 17.0}


@dataclass(frozen=True)
class Theme:
    name: str
    ground: str   # the panel's paper
    surface: str  # one step off the ground
    raised: str   # two steps off
    ink: str      # running text, titles, dots
    muted: str    # dates and secondary notes
    faint: str    # the empty days on the plate
    gold: str     # actions only


LIGHT = Theme("light", "#e2e2de", "#ecebe7", "#d3d3ce", "#1c1915", "#574e44", "#b9b6ae", "#c4922a")
DARK = Theme("dark", "#1c1915", "#23201c", "#2c2924", "#ecebe6", "#b3aa9e", "#3a362f", "#d6a43c")
THEMES = (LIGHT, DARK)


def esc(text: str) -> str:
    """Text made safe for SVG character data and attribute values."""
    return escape(text, {'"': "&quot;", "'": "&#39;"})


def clean(text: str) -> str:
    """Collapse whitespace and drop control characters, so a feed can't break a line or the XML."""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


def wrap(text: str, size: float, max_w: float, lines: int, weight: int = 400, tracking: float = 0.0) -> list[str]:
    """Break `text` into at most `lines` lines no wider than `max_w`. What doesn't fit ends in an ellipsis on the last
    line; a sentence that ends inside the space is kept whole and the rest dropped without one."""
    words, out, cur = clean(text).split(" "), [], ""
    for i, w in enumerate(words):
        trial = f"{cur} {w}".strip()
        if fonts.width(trial, size, weight, tracking) <= max_w:
            cur = trial
            continue
        if cur:
            out.append(cur)
        cur = w
        if len(out) == lines:
            break
        while fonts.width(cur, size, weight, tracking) > max_w and len(cur) > 1:  # one word wider than the line
            cur = cur[:-1]
    else:
        if cur:
            out.append(cur)
        return out
    out = out[:lines]
    last = out[-1]
    full = " ".join(out)
    # A whole sentence fits: stop there rather than trail off mid-thought.
    m = list(re.finditer(r"[.?!](?=\s|$)", full))
    if m and m[-1].end() > len(full) * 0.5:
        return _rewrap(full[: m[-1].end()], size, max_w, lines, weight, tracking)
    while last and fonts.width(last + "…", size, weight, tracking) > max_w:
        last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
    out[-1] = last.rstrip(" ,;:–—-") + "…"
    return out


def _rewrap(text: str, size, max_w, lines, weight, tracking) -> list[str]:
    out, cur = [], ""
    for w in text.split(" "):
        trial = f"{cur} {w}".strip()
        if fonts.width(trial, size, weight, tracking) <= max_w or not cur:
            cur = trial
        else:
            out.append(cur)
            cur = w
    out.append(cur)
    return out[:lines]


def fit(text: str, size: float, max_w: float, weight: int = 400, tracking: float = 0.0) -> str:
    """One line, cut with an ellipsis if it is wider than `max_w` (mid-word if need be: names, repo slugs)."""
    t = clean(text)
    if fonts.width(t, size, weight, tracking) <= max_w:
        return t
    while t and fonts.width(t + "…", size, weight, tracking) > max_w:
        t = t[:-1]
    return t.rstrip(" ,;:–—-") + "…"


class Doc:
    """An SVG document: a view box, a ground, CSS classes, and the text it carries (for the font subset)."""

    def __init__(self, w: float, h: float, theme: Theme, title: str):
        self.w, self.h, self.t, self.title = w, h, theme, title
        self.parts: list[str] = []
        self.text: list[str] = []
        self.sizes: list[float] = []
        self.css: list[str] = []

    def add(self, s: str) -> None:
        self.parts.append(s)

    def words(self, x: float, y: float, s: str, size: float, weight: int = 400, fill: str | None = None,
              anchor: str = "start", tracking: float = 0.0, cls: str = "", extra: str = "") -> None:
        """One line of type. Every call is counted against the smallest size the panel may show."""
        if not s:
            return
        self.text.append(s)
        self.sizes.append(size)
        ls = f' letter-spacing="{tracking}em"' if tracking else ""
        c = f' class="{cls}"' if cls else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size:g}" font-weight="{weight}" '
                 f'fill="{fill or self.t.ink}" text-anchor="{anchor}"{ls}{c}{extra}>{esc(s)}</text>')

    def render(self, ground: bool = True) -> str:
        bg = f'<rect width="{self.w:g}" height="{self.h:g}" fill="{self.t.ground}"/>' if ground else ""
        css = fonts.face("".join(self.text) + self.title) if self.text else ""
        css += (f"text{{font-family:'{fonts.FAMILY}',ui-sans-serif,system-ui,sans-serif;"
                "font-variant-numeric:tabular-nums;font-kerning:normal}")
        css += "".join(self.css)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w:g} {self.h:g}" '
                f'width="{self.w:g}" height="{self.h:g}" role="img" aria-label="{esc(self.title)}">'
                f"<title>{esc(self.title)}</title><style>{css}</style>{bg}{''.join(self.parts)}</svg>")
