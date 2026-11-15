"""Cut the pictures the static panels carry, from the studio site's public files (run locally; needs ffmpeg).

- The masthead: StillDrawn's inked panel est-tone-1 and six frames of its Runway Gen-4.5 burst clip, as the site's
  hero serves them, cut to 640 x 360 WebP.
- The selected work: one frame per featured entry, from /work.json, cut to 3:2 so a row of three lines up.

Every file is fetched from studionephele.com, so anyone can rebuild them from this repo alone.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = "https://studionephele.com"
PANEL = "/img/hero-est-tone-1-w960.webp"
CLIP = "/hero-frames/est-tone-1_burst_gen45/5362c995d6/1280/{k}.webp"
# Sprite slots k = 1..31 hold clip frames 4, 8, 12, 15 ... 120 (the site's data/hero.json); ending on 120 (four, to keep the masthead light).
SLOTS = [(1, 4), (11, 43), (21, 81), (31, 120)]
UA = {"User-Agent": "studio-nephele-profile/1 (+https://github.com/aaronlsmiles/aaronlsmiles)"}


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


def cut(data: bytes, out: Path, w: int, h: int, quality: int, zoom: float = 1.0, anchor: float = 0.5) -> None:
    """Crop to w:h (the middle, or `zoom` of it placed `anchor` of the way down), scale to w x h, encode WebP
    (libwebp's cwebp; ffprobe reads the size). zoom < 1 trims a film still's subtitle band."""
    with tempfile.NamedTemporaryFile(suffix=".webp") as f:
        f.write(data)
        f.flush()
        sw, sh = map(int, subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                          "stream=width,height", "-of", "csv=p=0", f.name],
                                         capture_output=True, text=True, check=True).stdout.strip().split(","))
        if sw * h > sh * w:  # wider than the target: trim the sides
            cw, ch = round(sh * w / h), sh
        else:
            cw, ch = sw, round(sw * h / w)
        cw, ch = round(cw * zoom), round(ch * zoom)
        x, y = (sw - cw) // 2, round((sh - ch) * anchor)
        subprocess.run(["cwebp", "-quiet", "-q", str(quality), "-m", "6", "-metadata", "none",
                        "-crop", str(x), str(y), str(cw), str(ch), "-resize", str(w), str(h), f.name, "-o", str(out)],
                       check=True)


def masthead() -> None:
    d = ROOT / "assets/src/masthead"
    d.mkdir(parents=True, exist_ok=True)
    cut(fetch(SITE + PANEL), d / "panel.webp", 640, 360, 42)
    clip = []
    for k, n in SLOTS:
        cut(fetch(SITE + CLIP.format(k=k)), d / f"f{n:03d}.webp", 640, 360, 42)
        clip.append({"frame": n, "file": f"f{n:03d}.webp"})
    (d / "frames.json").write_text(json.dumps({"panel": "panel.webp", "clip": clip,
                                               "source": SITE + "/work/stilldrawn",
                                               "credit": "StillDrawn, CC BY 4.0, doi:10.5281/zenodo.23072784"},
                                              indent=1) + "\n")


def tiles(feed: dict, featured: list[str], overrides: dict | None = None) -> None:
    d = ROOT / "assets/work"
    d.mkdir(parents=True, exist_ok=True)
    items = {w["id"]: w for w in feed["work"]}
    for fid in featured:
        o = (overrides or {}).get(fid)
        src = f"{SITE}/img/{o['id']}-w640.webp" if o else (items[fid]["frame"] or {}).get("src", "")
        if not src.startswith(SITE + "/"):
            raise SystemExit(f"{fid}: no frame on the site")
        cut(fetch(src), d / f"{fid}.webp", 600, 400, 62, (o or {}).get("zoom", 1.0), (o or {}).get("anchor", 0.5))
