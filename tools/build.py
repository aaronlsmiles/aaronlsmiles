#!/usr/bin/env python3
"""Build the profile: python3 tools/build.py [frames|static|live|all]

  frames  fetch and cut the pictures from studionephele.com (local; needs ffmpeg)
  static  the masthead and the button (local, after frames)
  live    the desk, the plate and README.md (the daily Action runs this)
  all     static, then live

Every SVG is drawn twice per width (light, dark) at two widths (wide, narrow).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ink import desk, fetch, masthead, plate, readme  # noqa: E402
from ink.svg import LIGHT, NARROW, THEMES, WIDE, Doc, fonts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config.json").read_text())
ASSETS = ROOT / "assets"
WIDTHS = {"wide": WIDE, "narrow": NARROW}


def write(name: str, draw) -> None:
    for wname, w in WIDTHS.items():
        for t in THEMES:
            (ASSETS / f"{name}-{wname}-{t.name}.svg").write_text(draw(w, t))


def button() -> None:
    """The one action: gold, square, the site's own button."""
    label, size, padx, h = "See the work", 18, 22, 44
    w = round(fonts.width(label, size, 600) + 2 * padx)
    d = Doc(w, h, LIGHT, label)
    d.add(f'<rect width="{w}" height="{h}" fill="{LIGHT.gold}"/>')
    d.words(padx, h / 2 + size * 0.36, label, size, 600, fill="#1c1915")
    (ASSETS / "button-work.svg").write_text(d.render(ground=False))


def static() -> None:
    write("masthead", masthead.draw)
    button()


def live(now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    feed, stale = fetch.work(CONFIG["feed"])
    repos, cal = fetch.github(CONFIG["user"], set(CONFIG["skip"]))
    total = cal.get("total")
    d = desk.build(feed, repos, now, stale)
    write("desk", lambda w, t: desk.draw(w, t, d))
    weeks = cal.get("weeks") or []
    write("plate", lambda w, t: plate.draw(w, t, weeks, total))
    row, names = readme.tiles(feed, CONFIG["featured"], CONFIG.get("frames"))
    days = [x for wk in weeks for x in wk]
    (ROOT / "README.md").write_text(readme.render({
        "masthead": readme.picture("masthead", masthead.alt(), "https://studionephele.com"),
        "desk": readme.picture("desk", desk.alt(d), "https://studionephele.com/#work"),
        "desk_note": d.stamp,
        "tiles": row,
        "tile_list": names,
        "plate": readme.picture("plate", plate.alt(days, total)),
        "plate_caption": readme.plate_caption(total, cal.get("private")),
    }))


def main(argv: list[str]) -> None:
    cmd = argv[1] if len(argv) > 1 else "all"
    if cmd == "frames":
        from ink import frames
        frames.masthead()
        frames.tiles(json.loads(fetch.CACHE.read_text()), CONFIG["featured"], CONFIG.get("frames"))  # the last good feed
    elif cmd == "static":
        static()
    elif cmd == "live":
        live()
    elif cmd == "all":
        static()
        live()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
