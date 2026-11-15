"""Render README.md from templates/README.md: the live alt text, the selected work and the plate's caption.

GitHub keeps <picture>, <source media> and width on images, and drops styles and scripts; every panel is offered in
four files (wide or narrow, light or dark) and the browser picks one. Nothing inside an <img> can be clicked, so each
link is its own image or its own words.
"""
from __future__ import annotations

from pathlib import Path

from .svg import clean, esc

ROOT = Path(__file__).resolve().parents[2]
NARROW_MQ = "(max-width: 600px)"


def picture(name: str, alt: str, href: str | None = None) -> str:
    a = esc(clean(alt))
    pic = (f"<picture>\n"
           f'<source media="{NARROW_MQ} and (prefers-color-scheme: dark)" srcset="assets/{name}-narrow-dark.svg">\n'
           f'<source media="{NARROW_MQ}" srcset="assets/{name}-narrow-light.svg">\n'
           f'<source media="(prefers-color-scheme: dark)" srcset="assets/{name}-wide-dark.svg">\n'
           f'<img src="assets/{name}-wide-light.svg" width="100%" alt="{a}">\n'
           f"</picture>")
    return f'<a href="{esc(href)}">\n{pic}\n</a>' if href else pic


def tiles(feed: dict, featured: list[str], overrides: dict | None = None) -> tuple[str, str]:
    """(the row of linked frames, the list that names them), both as HTML with every feed string escaped: Markdown
    escaping can be talked out of with a backslash, attribute escaping can't. `overrides` swaps an entry's frame for
    another of its own frames on the site (config.json `frames`), with that frame's alt text and model as recorded."""
    items = {w["id"]: w for w in feed["work"]}
    imgs, lines = [], []
    for fid in featured:
        w = items.get(fid)
        if not w or not (ROOT / f"assets/work/{fid}.webp").exists():
            continue
        f = (overrides or {}).get(fid) or w.get("frame") or {}
        href = esc(w["url"])
        imgs.append(f'<a href="{href}"><img src="assets/work/{fid}.webp" width="49%" '
                    f'alt="{esc(clean(f.get("alt") or w["title"]))}"></a>')
        made = f" Made with {esc(clean(f['model']))}." if f.get("model") else ""
        line = clean(w["line"])
        if line and line[-1] not in ".?!":
            line += "."
        lines.append(f'<li><a href="{href}"><strong>{esc(clean(w["title"]))}</strong></a>: {esc(line)}{made}</li>')
    return "<p>\n" + "\n".join(imgs) + "\n</p>", "<ul>\n" + "\n".join(lines) + "\n</ul>" if lines else ""


def plate_caption(total: int | None, private: int | None) -> str:
    if total is None:
        return "One dot a day; the bigger the dot, the busier the day."
    tail = f", {private:,} of them in private repos" if private else ""
    return f"{total:,} contributions in the last year{tail}. One dot a day; the bigger the dot, the busier the day."


def render(fill: dict[str, str]) -> str:
    text = (ROOT / "templates/README.md").read_text()
    for k, v in fill.items():
        text = text.replace("{{" + k + "}}", v)
    if "{{" in text:
        raise SystemExit(f"README template has an unfilled slot: {text[text.index('{{'):][:40]}")
    return text
