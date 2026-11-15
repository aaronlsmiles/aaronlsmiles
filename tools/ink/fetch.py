"""What the live panels read: the studio's Work list and GitHub's own record. Standard library only.

The site's feed is checked before it is trusted: its shape, its lengths, and every link and picture must be https on
the studio's own hosts (a link may also be one of the owner's GitHub repos). If it can't be fetched or doesn't pass
(a Cloudflare challenge page, a 5xx, a changed shape), the last good copy in data/work.json is used, the reason goes
to the log, and the panel says only how old its list is. GitHub errors stop the run, so a blank plate never lands.
"""
from __future__ import annotations

import http.client
import json
from datetime import datetime, timezone
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data/work.json"
FETCHED = ROOT / "data/fetched.txt"
UA = "studio-nephele-profile/1 (+https://github.com/aaronlsmiles/aaronlsmiles)"
KEYS = {"id", "title", "line", "year", "date", "inProgress", "url", "frame"}


def token() -> str | None:
    t = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if t:
        return t
    try:  # a local run: the personal account's token from gh, never another account's
        return subprocess.run(["gh", "auth", "token", "--user", "aaronlsmiles"], capture_output=True, text=True,
                              check=True, timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _get(url: str, data: bytes | None = None, headers: dict | None = None, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if urlsplit(r.geturl()).scheme != "https":  # urllib follows a redirect down to http; we don't
            raise urllib.error.URLError(f"redirected off https to {urlsplit(r.geturl()).netloc}")
        return r.read(MAX_BYTES + 1)[:MAX_BYTES + 1]


MAX_BYTES = 512 * 1024              # the real feed is under 10 KB
MAX_ITEMS = 100
MAX_LEN = {"id": 80, "title": 160, "line": 400, "date": 10, "url": 300, "alt": 400, "model": 80, "credit": 300}
BAD_URL_CHARS = re.compile(r"[\s()<>\"'\\`\x00-\x1f\x7f]")


def safe_url(u: object, frame: bool = False) -> bool:
    """An https link the README may carry: the studio's own hosts, or (for a link, not a picture) the owner's GitHub
    repos. Nothing that could close a Markdown link or an HTML attribute."""
    if not isinstance(u, str) or BAD_URL_CHARS.search(u):
        return False
    p = urlsplit(u)
    host = (p.hostname or "").lower()
    studio = host == "studionephele.com" or host.endswith(".studionephele.com")
    github = not frame and host == "github.com" and p.path.startswith("/aaronlsmiles/")
    return p.scheme == "https" and not p.username and not p.port and (studio or github)


def _text(v: object, key: str) -> bool:
    if not isinstance(v, str) or len(v) > MAX_LEN[key]:
        return False
    try:
        v.encode("utf-8")  # a lone surrogate would crash the write
    except UnicodeEncodeError:
        return False
    return True


def valid(feed: object) -> str:
    """'' when the feed has the shape the panels need, else what's wrong with it."""
    if not isinstance(feed, dict) or feed.get("version") != 1 or not isinstance(feed.get("work"), list):
        return "not a version 1 feed"
    if not feed["work"] or len(feed["work"]) > MAX_ITEMS:
        return "an empty or oversized work list"
    for w in feed["work"]:
        if not isinstance(w, dict) or not KEYS <= w.keys():
            return "an entry without the fields the panels use"
        if not all(_text(w[k], k) for k in ("id", "title", "line", "date", "url")):
            return "an entry with a field of the wrong type or length"
        if not isinstance(w["inProgress"], bool) or not isinstance(w["year"], (int, str)):
            return "an entry with a field of the wrong type or length"
        if not safe_url(w["url"]):
            return "an entry whose link isn't one of the studio's own"
        f = w["frame"]
        if f is not None:
            if not isinstance(f, dict) or not safe_url(f.get("src"), frame=True) or not _text(f.get("alt"), "alt"):
                return "an entry with a frame the panel can't use"
            if any(k in f and not _text(f[k], k) for k in ("model", "credit")):
                return "an entry with a frame the panel can't use"
    return ""


def _strip(feed: dict) -> dict:
    return {k: v for k, v in feed.items() if k != "fetched"}


def work(url: str) -> tuple[dict, str]:
    """(feed, '' or the 'as of' note). A fresh, valid feed replaces the cache only when its content changed, so a
    quiet day commits nothing; the day it was last read goes in data/fetched.txt."""
    try:
        feed = json.loads(_get(url, headers={"Accept": "application/json"}))
        problem = valid(feed) and "came back in a shape the panel can't read"
    except urllib.error.HTTPError as e:
        feed, problem = None, f"answered HTTP {e.code}"
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):  # incl. a body cut short
        feed, problem = None, "couldn't be reached"
    except (ValueError, RecursionError):  # not JSON (a challenge page, an error page), or absurdly nested
        feed, problem = None, "didn't send usable JSON"
    if not problem:
        feed = _strip(feed)
        old = json.loads(CACHE.read_text()) if CACHE.exists() else None
        if old is None or _strip(old) != feed:
            CACHE.write_text(json.dumps(feed, indent=1, ensure_ascii=False) + "\n")
        FETCHED.write_text(datetime.now(timezone.utc).strftime("%Y-%m-%d") + "\n")
        return feed, ""
    cached = _strip(json.loads(CACHE.read_text()))
    if valid(cached):
        raise SystemExit(f"the feed {problem}, and the cached copy is unusable too")
    day = FETCHED.read_text().strip() if FETCHED.exists() else ""
    print(f"work feed: {problem}; using the copy from {day or 'an earlier day'}")  # the Action's log, not the page
    try:
        return cached, f"Work list as of {int(day[8:10])} {MONTHS[int(day[5:7]) - 1]}."
    except (ValueError, IndexError):
        return cached, "Work list from an earlier day."


def github(user: str, skip: set[str]) -> tuple[list[dict], dict]:
    """(the user's public repos, newest push first, minus forks, archives and `skip`; the contribution calendar)."""
    t = token()
    auth = {"Authorization": f"Bearer {t}"} if t else {}
    raw = json.loads(_get(f"https://api.github.com/users/{user}/repos?type=owner&sort=pushed&per_page=40",
                          headers={"Accept": "application/vnd.github+json", **auth}))
    repos = [r for r in raw if not r.get("fork") and not r.get("archived") and not r.get("private")
             and r["name"] not in skip]
    if not t:
        return repos, {}
    q = ("query($u:String!){user(login:$u){contributionsCollection{restrictedContributionsCount "
         "contributionCalendar{totalContributions weeks{contributionDays{date weekday contributionCount}}}}}}")
    body = json.dumps({"query": q, "variables": {"u": user}}).encode()
    res = json.loads(_get("https://api.github.com/graphql", data=body,
                          headers={"Content-Type": "application/json", **auth}))
    if res.get("errors"):
        raise SystemExit(f"GitHub GraphQL: {res['errors'][0].get('message', 'error')}")
    cc = (((res.get("data") or {}).get("user") or {}).get("contributionsCollection")) or {}
    cal = cc.get("contributionCalendar") or {}
    if not cal.get("weeks"):
        raise SystemExit("GitHub GraphQL returned no contribution calendar; keeping yesterday's plate")
    weeks = [[{"date": d["date"], "weekday": d["weekday"], "count": d["contributionCount"]}
              for d in w["contributionDays"]] for w in cal.get("weeks", [])]
    return repos, {"weeks": weeks, "total": cal.get("totalContributions"),
                   "private": cc.get("restrictedContributionsCount")}
