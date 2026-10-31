"""Render the public website to static files for GitHub Pages.

Visits every public page in-process (like scripts/check_site.py) and writes it to the output
folder as an .html file; GitHub Pages serves /loefter/7 from loefter/7.html. The front-page
search gets a JSON index (sog.json) and runs in the browser (static/js/search.js).
Admin pages are not built: the admin page stays on the local app.

Any page that isn't HTTP 200, or that leaks template values, fails the build, so a broken
site is never published.

Usage: python -m scripts.build_static [--base plokOgDok] [--out site] [--lifters N]
       python -m scripts.build_static --serve 8040 --base plokOgDok    # preview a build
"""

import argparse
import json
import re
import shutil
import sys
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

from app import formatting
from app import main as app_main
from core.clubs import club_slug
from db import queries
from scripts.check_site import LEAKS, visible_text

# Root-relative URLs in attributes ("/loefter/7", not "//cdn..."), which need the sub-path
# GitHub Pages serves a project site under (/plokOgDok/...).
_ROOT_URL = re.compile(r'\b(href|src|action)="/(?!/)')


def with_base(html: str, base: str) -> str:
    return _ROOT_URL.sub(lambda m: f'{m[1]}="{base}/', html)


def page_file(out: Path, url: str) -> Path:
    """'/' -> index.html, '/loefter/7' -> loefter/7.html."""
    return out / f"{url.strip('/') or 'index'}.html"


def search_index() -> dict:
    """What the front-page search needs, already formatted for display."""
    clubs = [
        {
            "club": c["club"],
            "slug": club_slug(c["club"]),
            "active": c["active_lifters"],
            "lifters": formatting.num(c["lifters"]),
            "last": formatting.dk_date(c["last_date"]),
        }
        for c in queries.all_clubs()
        if club_slug(c["club"])
    ]
    lifters = [
        {
            "id": row["lifter_id"],
            "name": row["name"],
            "club": row["club"],
            "pr": formatting.num(row["pr_total"]),
            "last": formatting.dk_date(row["last_date"]),
        }
        for row in queries.search_index()
    ]
    return {"clubs": clubs, "lifters": lifters}


def page_urls(client_limit: int | None) -> list[str]:
    comps = queries._all("SELECT competition_id FROM vl.mv_competition_summary ORDER BY 1")
    lifters = queries._all("SELECT lifter_id FROM vl.mv_lifter_summary ORDER BY 1")
    if client_limit:
        lifters = lifters[:client_limit]
    urls = ["/", "/kalender"]
    urls += [f"/klub/{club_slug(c['club'])}" for c in queries.all_clubs() if club_slug(c["club"])]
    urls += [f"/staevne/{c['competition_id']}" for c in comps]
    urls += [f"/loefter/{row['lifter_id']}" for row in lifters]
    return urls


def build(out: Path, base: str, lifter_limit: int | None = None) -> list[str]:
    """Write the site to `out`. Returns the problems found (empty means publishable)."""
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(app_main.HERE / "static", out / "static")
    (out / ".nojekyll").touch()  # serve files as they are, no Jekyll processing

    app_main.templates.env.globals["static_site"] = True
    problems: list[str] = []
    try:
        with TestClient(app_main.app) as client:
            urls = page_urls(lifter_limit)
            for i, url in enumerate(urls, 1):
                r = client.get(url)
                if r.status_code != 200:
                    problems.append(f"{url}: HTTP {r.status_code}")
                    continue
                text = visible_text(r.text)
                problems += [f"{url}: {label} in page text" for p, label in LEAKS if p.search(text)]
                target = page_file(out, url)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(with_base(r.text, base), encoding="utf-8")
                if i % 200 == 0:
                    print(f"  {i}/{len(urls)} pages", flush=True)
            index = json.dumps(search_index(), ensure_ascii=False, separators=(",", ":"))
            (out / "sog.json").write_text(index, encoding="utf-8")
    finally:
        app_main.templates.env.globals["static_site"] = False
    print(f"Wrote {len(urls)} pages to {out}/")
    return problems


def serve(out: Path, base: str, port: int) -> None:
    """Serve a finished build the way GitHub Pages does: under `base`, /x -> x.html."""

    class Handler(SimpleHTTPRequestHandler):
        def translate_path(self, path: str) -> str:
            path = urlsplit(path).path
            if base and path.startswith(base):
                path = path[len(base) :] or "/"
            local = super().translate_path(path)
            if not Path(local).exists() and Path(local + ".html").is_file():
                return local + ".html"
            return local

    print(f"Serving {out}/ at http://127.0.0.1:{port}{base}/")
    ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(out))).serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="", help="sub-path the site is served under")
    parser.add_argument("--out", default="site", help="output folder (default: site)")
    parser.add_argument("--lifters", type=int, default=None, help="only the first N lifters")
    parser.add_argument("--serve", type=int, metavar="PORT", help="preview an existing build")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    base = "/" + args.base.strip("/") if args.base.strip("/") else ""
    if ":" in base or " " in base:
        # Git Bash on Windows turns "/plokOgDok" into "C:/Program Files/Git/plokOgDok".
        sys.exit(f"--base looks like a file path ({base!r}); pass it without the slash")
    if args.serve:
        serve(Path(args.out), base, args.serve)
        return
    start = time.monotonic()
    problems = build(Path(args.out), base, args.lifters)
    print(f"{len(problems)} problems in {time.monotonic() - start:.0f}s")
    for p in problems[:80]:
        print("  !", p)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
