"""On the desk: what the studio is making and what it pushed lately, as a ledger, redrawn every morning.

The work in progress comes from studionephele.com/work.json, in the site's own order; the pushes from GitHub. Titles
and dates only: the pictures and the one-liners live under Selected work, so the ledger stays a glance. Nothing is
typed by hand. When the site can't be reached the ledger draws the last copy it had and says how old it is.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from . import fonts
from .svg import NARROW, WIDE, Doc, Theme, clean, fit, wrap

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def when(iso: str, this_year: int | None = None) -> str:
    """'2026-11-14' -> '14 Nov 2026' ('14 Nov' in this_year), '2026-11' -> 'Nov 2026', '2026' -> '2026'."""
    parts = (iso or "").split("-")
    try:
        year = "" if this_year is not None and parts[0] == str(this_year) else f" {parts[0]}"
        if len(parts) > 1 and not 1 <= int(parts[1]) <= 12:  # MONTHS[-1] would answer Dec for month 0
            return ""
        if len(parts) == 3:
            return f"{int(parts[2])} {MONTHS[int(parts[1]) - 1]}{year}"
        if len(parts) == 2:
            return f"{MONTHS[int(parts[1]) - 1]}{year or ' ' + parts[0]}"
    except (ValueError, IndexError):
        return ""
    return parts[0] if parts[0].isdigit() else ""


# How many of each the ledger lists: the phone gets fewer, so the panel stays a glance rather than a page.
LIMITS = {WIDE: dict(making=6, pushed=6), NARROW: dict(making=4, pushed=3)}


@dataclass
class Item:
    title: str
    note: str  # the date, already worded


@dataclass
class Desk:
    making: list[Item]
    pushed: list[Item]
    stamp: str
    stale: str = ""  # "Work list as of 14 Nov." when the site's feed couldn't be read today


def build(feed: dict, repos: list[dict], now: datetime, stale: str = "") -> Desk:
    y = now.year
    making = [w for w in feed.get("work", []) if w.get("inProgress")]
    return Desk(
        making=[Item(clean(w["title"]), f"since {when(w['date'], y)}".strip()) for w in making],
        pushed=[Item(clean(r["name"]), f"{when(r['pushed_at'][:10], y)}") for r in repos],
        stamp=f"Redrawn {now.day} {MONTHS[now.month - 1]} {now.year} from the studio's Work list and GitHub.",
        stale=stale,
    )


def alt(d: Desk) -> str:
    """Everything the wide panel shows, as words, for anyone who can't see it."""
    lim = LIMITS[WIDE]

    def items(xs):
        return "; ".join(f"{i.title} ({i.note})" for i in xs) or "nothing"
    rest = len(d.making) - lim["making"]
    more = f", and {rest} more on the site" if rest > 0 else ""
    return clean(f"On the desk. In progress: {items(d.making[:lim['making']])}{more}. "
                 f"Pushed lately: {items(d.pushed[:lim['pushed']])}. {d.stale}")


def draw(width: int, theme: Theme, d: Desk) -> str:
    wide = width == WIDE
    lim = LIMITS[width]
    making, pushed = d.making[:lim["making"]], d.pushed[:lim["pushed"]]
    rest = len(d.making) - len(making)
    pad = 40 if wide else 20
    inner = width - 2 * pad
    s = dict(head=28, title=24, note=22, pitch=44) if wide else dict(head=21, title=18, note=17, pitch=34)
    doc = Doc(width, 100, theme, alt(d))

    def column(x: float, y: float, w: float, head: str, items: list[Item], tail: str = "") -> float:
        """A heading, then one row per item: the title, and its date at the right edge. Returns the last baseline."""
        y += s["head"]
        doc.words(x, y, head, s["head"], 600)
        y += 8
        for it in items or [Item("Nothing just now.", "")]:
            y += s["pitch"]
            nw = fonts.width(it.note, s["note"]) + (16 if it.note else 0)
            doc.words(x + w, y, it.note, s["note"], 400, fill=theme.muted, anchor="end")
            doc.words(x, y, fit(it.title, s["title"], w - nw, 600), s["title"], 600 if items else 400,
                      fill=theme.ink if items else theme.muted)
        if tail:
            y += s["pitch"]
            doc.words(x, y, tail, s["note"], 400, fill=theme.muted)
        return y

    more = f"And {rest} more on the site." if rest > 0 else ""
    y = pad - 6
    if wide:
        gap = 56
        lw = (inner - gap) * 0.56  # work titles run longer than repo names
        rw = inner - gap - lw
        y = max(column(pad, y, lw, "In progress", making, more), column(pad + lw + gap, y, rw, "Pushed lately", pushed))
    else:
        y = column(pad, y, inner, "In progress", making, more)
        y = column(pad, y + 22, inner, "Pushed lately", pushed)

    # The redraw's date goes in the README's words, not here, so the panel changes only when the ledger does.
    if d.stale:
        y += 44 if wide else 34
        for ln in wrap(d.stale, s["note"], inner, 2):
            doc.words(pad, y, ln, s["note"], 400, fill=theme.muted)
            y += s["note"] + 8
        y -= s["note"] + 8
    doc.h = round(y + pad)
    return doc.render()
