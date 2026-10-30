"""Visit every page of the website (in-process, against the real database) and report
problems: non-200 responses, leaked template values, and numbers that look wrong.

Usage: python -m scripts.check_site [--lifters N]   (default: all lifters)
"""

import argparse
import re
import sys
import time
from collections import Counter

from fastapi.testclient import TestClient

from app.main import app
from core.clubs import club_slug
from db import queries

# Text that should never reach a visitor.
LEAKS = [
    (re.compile(r"\bNone\b"), "Python None"),
    (re.compile(r"\bnan\b", re.I), "nan"),
    (re.compile(r"\{\{|\{%"), "template syntax"),
    (re.compile(r"Traceback|Internal Server Error"), "server error"),
    (re.compile(r"\bundefined\b"), "undefined"),
]


def visible_text(html: str) -> str:
    html = re.sub(r"<script\b.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<style\b.*?</style>", " ", html, flags=re.S | re.I)
    return re.sub(r"<[^>]+>", " ", html)


def check(client: TestClient, url: str, problems: list[str]) -> float:
    start = time.monotonic()
    r = client.get(url)
    elapsed = time.monotonic() - start
    if r.status_code != 200:
        problems.append(f"{url}: HTTP {r.status_code}")
        return elapsed
    text = visible_text(r.text)
    for pattern, label in LEAKS:
        if pattern.search(text):
            problems.append(f"{url}: {label} in page text")
    return elapsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lifters", type=int, default=None, help="only check the first N lifters")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    problems: list[str] = []
    times: Counter = Counter()
    slowest: list[tuple[float, str]] = []
    with TestClient(app) as client:
        comps = queries._all("SELECT competition_id FROM vl.mv_competition_summary ORDER BY 1")
        lifters = queries._all("SELECT lifter_id FROM vl.mv_lifter_summary ORDER BY 1")
        if args.lifters:
            lifters = lifters[: args.lifters]
        urls = ["/", "/sog?q=an", "/sog?q=aarhus", "/sog?q=zzzzzz", "/admin/login"]
        urls += [f"/klub/{club_slug(c['club'])}" for c in queries.all_clubs()]
        urls += [f"/staevne/{c['competition_id']}" for c in comps]
        urls += [f"/loefter/{row['lifter_id']}" for row in lifters]
        for i, url in enumerate(urls, 1):
            t = check(client, url, problems)
            times[url.split("/")[1] or "front"] += t
            slowest.append((t, url))
            if i % 200 == 0:
                print(f"  {i}/{len(urls)} pages, {len(problems)} problems so far", flush=True)

    print(f"Checked {len(urls)} pages. {len(problems)} problems.")
    for p in problems[:80]:
        print("  !", p)
    print("Slowest:", ", ".join(f"{u} {t:.2f}s" for t, u in sorted(slowest, reverse=True)[:5]))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
