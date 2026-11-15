# How the profile is built

`tools/build.py` draws every panel as SVG and fills `templates/README.md` to make `README.md`. Don't edit those
outputs by hand: change the template or `tools/ink/`, then rebuild. Each panel is drawn four times (wide and narrow,
light and dark) because GitHub's `<picture>` picks by screen width and colour scheme. Geist is cut down to each file's
characters and embedded, since an SVG shown through `<img>` can load nothing from outside.

## Running it

`tools/run.sh frames|static|live|all` runs `build.py` with the Action's pinned `fonttools` and `brotli` (needs `uv`).

- `frames`: fetch pictures from studionephele.com and cut them small. Local only; needs `ffmpeg` and `cwebp`.
- `static`: the masthead and the button, from those frames. Local only.
- `live`: the desk, the plate and `README.md`. Needs a GitHub token; locally it comes from
  `gh auth token --user aaronlsmiles`.
- `all`: `static`, then `live`.

## What runs daily

The Action (`.github/workflows/redraw.yml`, 06:17 UTC, or on a push to `tools/`, `templates/`, `config.json` or
`fonts/`) runs `live` only. It reads the studio's `work.json` (falling back to the last good copy in `data/work.json`,
and saying so on the desk), the public repos and the contribution calendar, then commits `README.md`, `assets/` and
`data/` if they changed. On failure it opens, or comments on, an issue labelled `redraw`.

## Changing the featured work

In `config.json`, `featured` lists the work ids shown under "Selected work", in order; each needs
`assets/work/<id>.webp`. `frames` swaps an id's picture for another frame from the site (its `id`, `alt`, and optional
`model`, `zoom`, `anchor`). Then run `tools/run.sh frames`, then `tools/run.sh live`.

## Previewing and testing

`python3 tools/preview.py` renders `README.md` through GitHub's Markdown API (needs `gh`). Then run
`python3 -m http.server` in the repo root and open `/preview/`.

`uv run --no-project --with fonttools==4.67.0 --with brotli==1.2.0 --with pytest==8.3.4 python -m pytest -q`
runs the offline tests. They write nothing into `assets/`, and the Action doesn't run them.
