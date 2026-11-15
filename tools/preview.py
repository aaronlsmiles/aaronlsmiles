#!/usr/bin/env python3
"""Preview README.md as GitHub would show it: python3 tools/preview.py  ->  preview/index.html

The markdown goes through GitHub's own renderer (`gh api markdown`, which sanitises as github.com does), then into a
page styled with github-markdown-css at the width of a profile README. Open it with a local server from the repo root
(python3 -m http.server) so the relative image paths resolve; switch the system theme to see the dark files.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = "https://cdn.jsdelivr.net/npm/github-markdown-css@5.8.1/github-markdown.css"

html = subprocess.run(["gh", "api", "-X", "POST", "markdown", "-f", "mode=gfm", "-f", "context=aaronlsmiles/aaronlsmiles",
                       "-F", f"text=@{ROOT / 'README.md'}"], capture_output=True, text=True, check=True).stdout
page = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Profile preview</title><link rel="stylesheet" href="{CSS}">
<style>
:root{{color-scheme:light dark}}
body{{margin:0;background:#fff}}
@media (prefers-color-scheme:dark){{body{{background:#0d1117}}}}
.wrap{{max-width:848px;margin:24px auto;padding:0 16px}}
.box{{border:1px solid #d1d9e0;border-radius:6px;padding:24px}}
@media (prefers-color-scheme:dark){{.box{{border-color:#3d444d}}}}
@media (max-width:767px){{.wrap{{margin:16px auto}} .box{{padding:16px}}}}
</style></head><body><div class="wrap"><div class="box markdown-body">{html}</div></div></body></html>"""
out = ROOT / "preview"
out.mkdir(exist_ok=True)
(out / "index.html").write_text(page.replace('src="assets/', 'src="../assets/').replace('srcset="assets/', 'srcset="../assets/'))
print(out / "index.html")
