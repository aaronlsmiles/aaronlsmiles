"""Offline tests for the profile generator: python3 -m pytest -q  (see tools/README.md for the pinned command).

Nothing here touches the network or writes into assets/: panels are drawn from fixtures into a temp directory, and
every fetch is patched. The daily Action does not run these; they are for local changes.
"""
from __future__ import annotations

import http.client
import json
import re
import sys
import urllib.error
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build  # noqa: E402
from ink import desk, fetch, fonts, plate, readme  # noqa: E402
from ink.svg import DARK, LIGHT, MIN_TEXT, NARROW, THEMES, WIDE  # noqa: E402

SVG = "{http://www.w3.org/2000/svg}"
NOW = datetime(2026, 11, 15, 7, 0, tzinfo=timezone.utc)
FEED = json.loads((ROOT / "data/work.json").read_text())
PANELS = ("masthead", "desk", "plate")
VARIANTS = [(w, t) for w in ("wide", "narrow") for t in ("light", "dark")]
SIZE = {"wide": WIDE, "narrow": NARROW}

NASTY = '<script>alert(1)</script> & "double" \'single\' </text><text>'
LONG = "x" * 300                                    # one unbreakable run
LONG_WORDS = " ".join(["wandering"] * 60)           # a long sentence
EMOJI = "🎨 Ink 🖋️ 日本語 ✨ naïve café"


def repo(name: str = "some-repo", desc: str | None = "A repo.", pushed: str = "2026-11-14T10:00:00Z") -> dict:
    return {"name": name, "description": desc, "pushed_at": pushed}


REPOS = [repo("alpha", "First thing."), repo("beta", None), repo("gamma", "Third thing, a bit longer than the others.")]


def calendar(weeks: int = 53) -> list[list[dict]]:
    """A year of days, Sunday first, with a spread of counts."""
    start = date(2026, 11, 15) - timedelta(days=7 * weeks - 1)
    start -= timedelta(days=(start.weekday() + 1) % 7)  # back to a Sunday
    out = []
    for w in range(weeks):
        out.append([{"date": (start + timedelta(days=7 * w + d)).isoformat(), "weekday": d,
                     "count": (w * 7 + d) % 11 if (w + d) % 3 else 0} for d in range(7)])
    return out


CAL = {"weeks": calendar(), "total": 1234, "private": 56}


def item(i: int, title: str = "Title", line: str = "A line.", progress: bool = True, day: str = "2026-11-01") -> dict:
    return {"id": f"item-{i}", "title": title, "line": line, "year": 2026, "date": day, "inProgress": progress,
            "url": f"https://studionephele.com/work/item-{i}", "frame": None}


def feed_of(*items: dict) -> dict:
    return {"version": 1, "site": "https://studionephele.com", "work": list(items)}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a test reached for the network")
    monkeypatch.setattr(fetch, "_get", boom)
    monkeypatch.setattr("urllib.request.urlopen", boom)
    monkeypatch.setattr(fetch, "token", lambda: None)


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    """The whole build (static + live) from fixtures, into a temp tree; the real assets/ and README.md stay put."""
    root = tmp_path_factory.mktemp("site")
    (root / "assets").mkdir()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(build, "ROOT", root)
        mp.setattr(build, "ASSETS", root / "assets")
        mp.setattr(fetch, "CACHE", root / "work.json")
        mp.setattr(fetch, "work", lambda url: (FEED, ""))
        mp.setattr(fetch, "github", lambda user, skip: (REPOS, CAL))
        build.static()
        build.live(NOW)
    return root


# ---------------------------------------------------------------- helpers

def svg_files(root: Path) -> list[Path]:
    return sorted((root / "assets").glob("*.svg"))


def texts(svg: str) -> list[dict]:
    """Every <text>: where it starts, how big it is, and how wide the font says it is."""
    root = ET.fromstring(svg)
    out = []
    for t in root.iter(f"{SVG}text"):
        s = "".join(t.itertext())
        size = float(t.get("font-size"))
        weight = int(t.get("font-weight", 400))
        track = float((t.get("letter-spacing") or "0em").removesuffix("em"))
        out.append(dict(x=float(t.get("x")), size=size, anchor=t.get("text-anchor", "start"), text=s,
                        w=fonts.width(s, size, weight, track)))
    return out


def view_width(svg: str) -> float:
    return float(ET.fromstring(svg).get("viewBox").split()[2])


def assert_within(svg: str, tol: float = 2.0) -> None:
    vw = view_width(svg)
    for t in texts(svg):
        if t["anchor"] == "end":
            lo, hi = t["x"] - t["w"], t["x"]
        elif t["anchor"] == "middle":
            lo, hi = t["x"] - t["w"] / 2, t["x"] + t["w"] / 2
        else:
            lo, hi = t["x"], t["x"] + t["w"]
        assert lo >= -tol and hi <= vw + tol, f"{t['text'][:40]!r} spans {lo:.0f}..{hi:.0f} in a {vw:g} px panel"


def assert_safe(svg: str, width: int) -> None:
    ET.fromstring(svg)  # parses as XML
    assert "<script" not in svg.lower()
    assert_within(svg)
    assert all(t["size"] >= MIN_TEXT[width] for t in texts(svg))


def draw_all(d: desk.Desk) -> list[tuple[int, str]]:
    return [(w, desk.draw(w, t, d)) for w in (WIDE, NARROW) for t in THEMES]


# ---------------------------------------------------------------- every SVG after a build

def test_every_panel_has_four_variants(built):
    names = {p.name for p in svg_files(built)}
    for panel in PANELS:
        for w, t in VARIANTS:
            assert f"{panel}-{w}-{t}.svg" in names
    assert "button-work.svg" in names


def test_svgs_parse_and_load_nothing_outside(built):
    for p in svg_files(built):
        s = p.read_text()
        root = ET.fromstring(s)
        assert root.tag == f"{SVG}svg", p.name
        assert "@import" not in s, p.name
        assert 'href="http' not in s and "href='http" not in s, p.name
        assert "url(http" not in s and "url('http" not in s and 'url("http' not in s, p.name
        for el in root.iter():
            for k, v in el.attrib.items():
                if k.endswith("href"):
                    assert v.startswith("data:"), f"{p.name}: {k}={v[:40]}"
        assert "<script" not in s.lower(), p.name


def test_svgs_stay_under_budget(built):
    for p in svg_files(built):
        limit = 300_000 if p.name.startswith("masthead") else 80_000
        assert p.stat().st_size <= limit, f"{p.name} is {p.stat().st_size} bytes"


@pytest.mark.parametrize("panel", PANELS)
@pytest.mark.parametrize("wname,theme", VARIANTS)
def test_smallest_type_and_view_box(built, panel, wname, theme):
    svg = (built / f"assets/{panel}-{wname}-{theme}.svg").read_text()
    assert view_width(svg) == SIZE[wname]
    sizes = [t["size"] for t in texts(svg)]
    assert sizes and min(sizes) >= MIN_TEXT[SIZE[wname]], f"smallest is {min(sizes)}"


@pytest.mark.parametrize("panel", PANELS)
@pytest.mark.parametrize("wname,theme", VARIANTS)
def test_built_panels_keep_text_in_the_box(built, panel, wname, theme):
    assert_within((built / f"assets/{panel}-{wname}-{theme}.svg").read_text())


# ---------------------------------------------------------------- the masthead's motion

def _media_block(css: str) -> tuple[str, str]:
    """(the @media (prefers-reduced-motion:no-preference){...} block, the CSS without it)."""
    head = "@media (prefers-reduced-motion:no-preference){"
    i = css.index(head)
    depth, j = 0, i + len(head) - 1
    for j in range(i + len(head) - 1, len(css)):
        depth += {"{": 1, "}": -1}.get(css[j], 0)
        if depth == 0:
            break
    return css[i:j + 1], css[:i] + css[j + 1:]


@pytest.mark.parametrize("wname,theme", VARIANTS)
def test_masthead_animation_only_when_motion_is_welcome(built, wname, theme):
    svg = (built / f"assets/masthead-{wname}-{theme}.svg").read_text()
    css = "".join(ET.fromstring(svg).find(f"{SVG}style").itertext())
    css = re.sub(r"base64,[A-Za-z0-9+/=]+", "base64,", css)  # the font is not CSS we wrote
    inside, outside = _media_block(css)
    assert "animation" in inside and "@keyframes" in inside
    assert "animation" not in outside and "@keyframes" not in outside
    assert ".fr.end{opacity:1}" in outside, "the end frame must show when nothing moves"
    assert ".ct.end{opacity:1}" in outside, "its caption too"
    assert css.count("@media") == 1


# ---------------------------------------------------------------- escaping and worst cases

NASTY_TITLES = [NASTY, LONG, LONG_WORDS, EMOJI, "", "&amp; &lt;b&gt;"]


@pytest.mark.parametrize("title", NASTY_TITLES)
def test_desk_survives_nasty_text(title):
    feed = feed_of(item(1, title, title, True), item(2, title, title, True), item(3, title, title, False, "2026-10-01"))
    repos = [repo(title[:80] or "r", title), repo(LONG, LONG)]
    d = desk.build(feed, repos, NOW, stale=f"The work list is old: {title}")
    for w, svg in draw_all(d):
        assert_safe(svg, w)
        if "<script" in title:
            assert "&lt;script&gt;" in svg  # shown as text, escaped


def test_desk_zero_in_progress():
    d = desk.build(feed_of(item(1, progress=False), item(2, progress=False)), [], NOW)
    for w, svg in draw_all(d):
        assert_safe(svg, w)
        assert "Nothing just now." in svg


def test_desk_twenty_in_progress():
    feed = feed_of(*[item(i, f"Card number {i}", "One line of words that wraps on a narrow panel, twice over, maybe.")
                     for i in range(20)])
    d = desk.build(feed, REPOS, NOW)
    for w, svg in draw_all(d):
        assert_safe(svg, w)
    assert "And 14 more on the site." in desk.draw(WIDE, LIGHT, d)
    assert "And 16 more on the site." in desk.draw(NARROW, DARK, d)


def test_desk_empty_repos():
    d = desk.build(FEED, [], NOW)
    assert "Nothing just now." in desk.draw(WIDE, LIGHT, d)
    for w, svg in draw_all(d):
        assert_safe(svg, w)


def test_desk_stale_message_is_drawn():
    d = desk.build(FEED, REPOS, NOW, "Work list as of 14 Nov.")
    for w, svg in draw_all(d):
        assert_safe(svg, w)
        assert "Work list as of 14 Nov." in " ".join(t["text"] for t in texts(svg))


def test_desk_label_is_escaped():
    d = desk.build(feed_of(item(1, NASTY, NASTY)), REPOS, NOW)
    svg = desk.draw(WIDE, LIGHT, d)
    assert 'aria-label="' in svg and "<script" not in svg
    ET.fromstring(svg)


def test_plate_empty_calendar_and_total_none():
    for w in (WIDE, NARROW):
        for t in THEMES:
            for weeks, total in (([], None), ([], 0), ([[]], None), (calendar(1), None)):
                assert_safe(plate.draw(w, t, weeks, total), w)
    assert "no contribution data" in plate.alt([], None)


def test_plate_all_quiet_and_one_busy_day():
    quiet = [[{"date": f"2026-0{1 + w % 9}-0{1 + d}", "weekday": d, "count": 0} for d in range(7)] for w in range(20)]
    busy = [[dict(day, count=10**6 if (i, j) == (3, 3) else 0) for j, day in enumerate(wk)]
            for i, wk in enumerate(quiet)]
    for weeks in (quiet, busy):
        for w in (WIDE, NARROW):
            assert_safe(plate.draw(w, LIGHT, weeks, 10**6), w)


def test_plate_levels():
    assert plate.levels([]) == (1, 2, 3)
    assert plate.levels([0, 0]) == (1, 2, 3)
    assert plate.levels([0, 5]) == (5, 5, 5)


def test_tiles_escape_what_the_feed_says():
    feed = feed_of(item(1, NASTY, NASTY))
    feed["work"][0]["id"] = "stilldrawn"
    row, names = readme.tiles(feed, ["stilldrawn"], {"stilldrawn": {"alt": NASTY, "model": NASTY}})
    for out in (row, names):
        assert "<script" not in out and "<text>" not in out
    assert 'alt="&lt;script&gt;' in row
    assert "&lt;script&gt;" in names


def test_tiles_skip_unknown_and_missing_pictures():
    row, names = readme.tiles(feed_of(item(1)), ["nope", "item-1"], None)  # no assets/work/item-1.webp
    assert row == "<p>\n\n</p>" and names == ""


def test_tiles_link_text_cannot_break_out():
    """The list is HTML with every feed string escaped: a backslash can't talk its way out as it can in Markdown."""
    for title in ("A [bracketed] title", "x\\](http://evil.example/)", 'x" onmouseover="y', "<img src=x>"):
        feed = feed_of(item(1, title, "A line"))
        feed["work"][0]["id"] = "stilldrawn"
        _, names = readme.tiles(feed, ["stilldrawn"], None)
        assert names.startswith('<ul>\n<li><a href="https://studionephele.com/work/item-1"><strong>')
        assert "<img" not in names and 'onmouseover="' not in names and names.count("<a ") == 1


# ---------------------------------------------------------------- the feed and its fallback

@pytest.fixture
def cache(tmp_path, monkeypatch):
    p = tmp_path / "work.json"
    p.write_text((ROOT / "data/work.json").read_text())
    monkeypatch.setattr(fetch, "CACHE", p)
    monkeypatch.setattr(fetch, "FETCHED", tmp_path / "fetched.txt")
    return p


def raising(exc):
    def get(*a, **k):
        raise exc
    return get


@pytest.mark.parametrize("get,reason", [
    (raising(urllib.error.HTTPError("u", 404, "Not Found", {}, None)), "HTTP 404"),
    (raising(urllib.error.HTTPError("u", 503, "Unavailable", {}, None)), "HTTP 503"),
    (raising(urllib.error.URLError("dns")), "couldn't be reached"),
    (raising(TimeoutError()), "couldn't be reached"),
    (raising(ConnectionResetError()), "couldn't be reached"),
    (raising(http.client.IncompleteRead(b"")), "couldn't be reached"),
    (lambda *a, **k: b"<html>Just a moment...</html>", "didn't send usable JSON"),
    (lambda *a, **k: b"\xff\xfe", "didn't send usable JSON"),
    (lambda *a, **k: b"[" * 100000 + b"]" * 100000, "didn't send usable JSON"),
    (lambda *a, **k: b'{"version": 2}', "shape the panel can't read"),
    (lambda *a, **k: b"[]", "shape the panel can't read"),
    (lambda *a, **k: json.dumps(feed_of()).encode(), "shape the panel can't read"),
])
def test_feed_falls_back_to_the_cache(monkeypatch, capsys, cache, get, reason):
    before = cache.read_text()
    monkeypatch.setattr(fetch, "_get", get)
    feed, stale = fetch.work("https://studionephele.com/work.json")
    assert feed == json.loads(before)
    assert stale.startswith("Work list") and "HTTP" not in stale, "the public panel gives a date, never a status code"
    assert reason in capsys.readouterr().out, "the reason goes to the Action's log"
    assert cache.read_text() == before, "a bad feed must never overwrite the good copy"


def test_a_good_feed_is_cached(monkeypatch, cache):
    fresh = feed_of(item(1, "Fresh"))
    monkeypatch.setattr(fetch, "_get", lambda *a, **k: json.dumps(fresh).encode())
    feed, stale = fetch.work("https://studionephele.com/work.json")
    assert stale == "" and feed == fresh and json.loads(cache.read_text()) == fresh
    assert len(fetch.FETCHED.read_text().strip()) == 10
    before = cache.stat().st_mtime_ns
    fetch.work("https://studionephele.com/work.json")
    assert cache.stat().st_mtime_ns == before, "an unchanged feed leaves the cache alone (nothing to commit)"


def test_unusable_feed_and_unusable_cache_stops_the_build(monkeypatch, cache):
    cache.write_text('{"version": 2}')
    monkeypatch.setattr(fetch, "_get", raising(urllib.error.URLError("dns")))
    with pytest.raises(SystemExit):
        fetch.work("https://studionephele.com/work.json")


def test_valid_rejects_a_link_that_is_not_https():
    assert fetch.valid(feed_of(item(1))) == ""
    bad = feed_of(item(1))
    for u in ("http://studionephele.com/work/x", "javascript:alert(1)", "https://evil.example/x",
              "https://studionephele.com/x) ![p](https://evil.example/pixel.png)",
              "https://studionephele.com/x\n\n# Owned\n\n<img src=x>", 'https://studionephele.com/x"><img src=x>',
              "https://studionephele.com.evil.example/", "https://user@studionephele.com/",
              "https://github.com/someoneelse/repo", "data:text/html,hi"):
        bad["work"][0]["url"] = u
        assert fetch.valid(bad), u
    for u in ("https://studionephele.com/work/x", "https://stilldrawn.studionephele.com/",
              "https://github.com/aaronlsmiles/loopcutter"):
        bad["work"][0]["url"] = u
        assert fetch.valid(bad) == "", u
    bad["work"][0]["url"] = "https://studionephele.com/work/x"
    bad["work"][0]["frame"] = {"src": "https://github.com/aaronlsmiles/x.png", "alt": "a picture"}
    assert fetch.valid(bad), "pictures come from the studio's hosts only"
    bad["work"][0]["frame"] = "a string"
    assert fetch.valid(bad)
    bad["work"][0]["frame"] = None
    bad["work"][0]["title"] = "x" * 10000
    assert fetch.valid(bad), "lengths are capped"
    bad["work"][0]["title"] = "\ud800"
    assert fetch.valid(bad), "a lone surrogate is refused"


@pytest.mark.parametrize("mutate,why", [
    (lambda f: f.pop("version"), "version 1"),
    (lambda f: f.__setitem__("work", "nope"), "version 1"),
    (lambda f: f["work"][0].pop("line"), "fields"),
    (lambda f: f["work"][0].__setitem__("title", 5), "wrong type"),
])
def test_valid_rejects_a_changed_shape(mutate, why):
    f = feed_of(item(1))
    mutate(f)
    assert why in fetch.valid(f)


def test_valid_rejects_non_feeds():
    assert fetch.valid(None) and fetch.valid([]) and fetch.valid({"version": 1, "work": []})


def test_the_committed_cache_is_a_valid_feed():
    assert fetch.valid(FEED) == ""


# ---------------------------------------------------------------- the README

def test_readme_is_fully_filled_and_links_are_https(built):
    text = (built / "README.md").read_text()
    assert "{{" not in text and "}}" not in text
    hrefs = re.findall(r'href="([^"]+)"', text)
    md = re.findall(r"\]\(([^)\s]+)\)", text)
    assert hrefs and md
    for url in hrefs + md:
        assert url.startswith("https://"), url
    assert "http://" not in text
    assert "<script" not in text.lower()


@pytest.mark.parametrize("panel", PANELS)
def test_readme_offers_all_four_files_of_each_panel(built, panel):
    text = (built / "README.md").read_text()
    lines = [ln for ln in text.splitlines() if f"assets/{panel}-" in ln]
    assert len(lines) == 4
    assert sum(ln.startswith("<source") for ln in lines) == 3 and sum(ln.startswith("<img") for ln in lines) == 1
    for w, t in VARIANTS:
        assert sum(f"assets/{panel}-{w}-{t}.svg" in ln for ln in lines) == 1


def test_readme_images_exist(built):
    text = (built / "README.md").read_text()
    for src in re.findall(r'(?:src|srcset)="(assets/[^"]+)"', text):
        assert (built / src).exists() or (ROOT / src).exists(), src


def test_readme_template_with_an_unfilled_slot_fails():
    with pytest.raises(SystemExit):
        readme.render({"masthead": "x"})


def test_plate_caption():
    assert readme.plate_caption(None, None).startswith("One dot a day")
    assert readme.plate_caption(1234, None).startswith("1,234 contributions in the last year.")
    assert "56 of them in private repos" in readme.plate_caption(1234, 56)


# ---------------------------------------------------------------- dates

@pytest.mark.parametrize("iso,year,want", [
    ("2026-11-14", 2026, "14 Nov"),
    ("2026-11-14", 2025, "14 Nov 2026"),
    ("2026-11-14", None, "14 Nov 2026"),
    ("2026-01-05", 2026, "5 Jan"),
    ("2026-11", 2026, "Nov 2026"),
    ("2026-11", None, "Nov 2026"),
    ("2025-03", 2026, "Mar 2025"),
    ("2026", 2026, "2026"),
    ("2026", None, "2026"),
    ("garbage", 2026, ""),
    ("", 2026, ""),
    (None, 2026, ""),
    ("2026-13-01", 2026, ""),
    ("2026-00", 2026, ""),
    ("2026-xx", 2026, ""),
    ("2026-11-xx", 2026, ""),
])
def test_when(iso, year, want):
    assert desk.when(iso, year) == want


def test_stale_note_dates_the_cached_copy(monkeypatch, cache):
    cache.write_text(json.dumps(feed_of(item(1))))
    fetch.FETCHED.write_text("2026-11-14\n")
    monkeypatch.setattr(fetch, "_get", raising(urllib.error.URLError("dns")))
    assert fetch.work("https://studionephele.com/work.json")[1] == "Work list as of 14 Nov."


def test_graphql_errors_stop_the_run(monkeypatch):
    monkeypatch.setattr(fetch, "token", lambda: "t")
    def get(url, data=None, headers=None, timeout=20):
        if "graphql" in url:
            return json.dumps({"data": None, "errors": [{"message": "Something went wrong"}]}).encode()
        return b"[]"
    monkeypatch.setattr(fetch, "_get", get)
    with pytest.raises(SystemExit, match="GraphQL"):
        fetch.github("aaronlsmiles", set())


def test_an_empty_calendar_stops_the_run(monkeypatch):
    monkeypatch.setattr(fetch, "token", lambda: "t")
    def get(url, data=None, headers=None, timeout=20):
        if "graphql" in url:
            return json.dumps({"data": {"user": {"contributionsCollection": {"contributionCalendar": {"weeks": []}}}}}).encode()
        return b"[]"
    monkeypatch.setattr(fetch, "_get", get)
    with pytest.raises(SystemExit, match="no contribution calendar"):
        fetch.github("aaronlsmiles", set())
