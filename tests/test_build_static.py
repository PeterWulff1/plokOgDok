from pathlib import Path

from scripts.build_static import page_file, with_base


def test_with_base_prefixes_root_relative_urls_only():
    html = (
        '<a href="/loefter/7">x</a> <a href="/#sog">s</a> <img src="/static/a.png">'
        ' <script src="https://unpkg.com/htmx.org"></script> <a href="//cdn.x/y">c</a>'
        ' <a href="#top">t</a> <input data-index="/sog.json">'
    )
    assert with_base(html, "/plokOgDok") == (
        '<a href="/plokOgDok/loefter/7">x</a> <a href="/plokOgDok/#sog">s</a>'
        ' <img src="/plokOgDok/static/a.png">'
        ' <script src="https://unpkg.com/htmx.org"></script> <a href="//cdn.x/y">c</a>'
        ' <a href="#top">t</a> <input data-index="/sog.json">'
    )
    assert with_base(html, "") == html


def test_page_file():
    out = Path("site")
    assert page_file(out, "/") == out / "index.html"
    assert page_file(out, "/kalender") == out / "kalender.html"
    assert page_file(out, "/loefter/7") == out / "loefter" / "7.html"
