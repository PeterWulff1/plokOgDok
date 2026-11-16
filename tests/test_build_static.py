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


def test_not_found_page_is_written_for_github_pages(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app import main as app_main
    from scripts.build_static import _render_not_found

    monkeypatch.setattr(app_main.queries, "open_pool", lambda url=None: None)
    monkeypatch.setattr(app_main.queries, "close_pool", lambda: None)
    monkeypatch.setattr(app_main.admin_store, "close_pool", lambda: None)
    with TestClient(app_main.app) as client:
        assert _render_not_found(client, tmp_path, "/plokOgDok") == []
    html = (tmp_path / "404.html").read_text(encoding="utf-8")
    assert "Ikke godkendt" in html and 'href="/plokOgDok/#sog"' in html
    assert 'src="/plokOgDok/static/js/site.js' in html
