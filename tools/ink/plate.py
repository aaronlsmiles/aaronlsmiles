"""The year in ink: GitHub's contribution calendar as a halftone screen.

One dot a day, its size set by how busy the day was against the year's own spread (quartiles of the busy days, as
GitHub's own graph does), so a quiet year and a loud one both read as tone rather than as an empty grid.
A day with nothing is a pinprick in the faint ink, so the screen stays whole.
"""
from __future__ import annotations

from .desk import MONTHS
from .svg import NARROW, WIDE, Doc, Theme


def levels(counts: list[int]) -> tuple[float, float, float]:
    busy = sorted(c for c in counts if c > 0)
    if not busy:
        return (1, 2, 3)
    q = lambda p: busy[min(int(p * len(busy)), len(busy) - 1)]  # noqa: E731
    return (q(0.25), q(0.5), q(0.75))


def alt(days: list[dict], total: int | None) -> str:
    if not days:
        return "The year in ink: no contribution data today."
    busiest = max(days, key=lambda d: d["count"])
    t = f"{total:,} contributions" if total is not None else "contributions"
    return (f"The year in ink: {t} from {days[0]['date']} to {days[-1]['date']}, one dot a day, bigger on busier "
            f"days. The busiest day was {busiest['date']}, with {busiest['count']}.")


def draw(width: int, theme: Theme, weeks: list[list[dict]], total: int | None) -> str:
    wide = width == WIDE
    pad = 40 if wide else 20
    weeks = weeks[-53:] if wide else weeks[-26:]
    inner = width - 2 * pad
    n = max(len(weeks), 1)
    cell = inner / n
    rmax = cell * 0.46
    lab = 22 if wide else 17
    days = [d for w in weeks for d in w]
    q1, q2, q3 = levels([d["count"] for d in days])
    radii = (rmax * 0.34, rmax * 0.55, rmax * 0.76, rmax)
    top = pad
    h = top + 7 * cell + 18 + lab + pad
    doc = Doc(width, round(h), theme, alt(days, total))
    dots = []
    for i, w in enumerate(weeks):
        for d in w:
            row = d.get("weekday", 0)
            cx, cy = pad + (i + 0.5) * cell, top + (row + 0.5) * cell
            c = d["count"]
            if c <= 0:
                dots.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{max(rmax * 0.16, 1.1):.2f}" fill="{theme.faint}"/>')
                continue
            r = radii[0] if c <= q1 else radii[1] if c <= q2 else radii[2] if c <= q3 else radii[3]
            dots.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.2f}" fill="{theme.ink}"/>')
    doc.add("".join(dots))
    # Month names under the first week of each month, where there's room for them.
    last_x, prev = -1e9, None
    for i, w in enumerate(weeks):
        if not w:
            continue
        mon = w[-1]["date"][5:7]  # the month the week ends in
        new = prev is not None and mon != prev
        prev = mon
        x = pad + i * cell
        if not new or x - last_x < lab * 2.6 or x + lab * 1.8 > width - pad + 4:
            continue
        doc.words(x, top + 7 * cell + 18 + lab * 0.8, MONTHS[int(mon) - 1], lab, 400, fill=theme.muted)
        last_x = x
    return doc.render()
