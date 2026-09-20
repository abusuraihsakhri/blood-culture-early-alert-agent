"""Static GitHub Pages smoke tests."""

from pathlib import Path


DOCS = Path(__file__).resolve().parents[1] / "docs"


def test_pages_assets_exist():
    assert (DOCS / "index.html").is_file()
    assert (DOCS / "styles.css").is_file()
    assert (DOCS / "app.js").is_file()


def test_pages_has_primary_analyze_action_and_theme_toggle():
    html = (DOCS / "index.html").read_text(encoding="utf-8")
    assert ">Analyze<" in html
    assert 'id="themeToggle"' in html
    assert 'id="analysisForm"' in html


def test_pages_analysis_is_local_only():
    js = (DOCS / "app.js").read_text(encoding="utf-8")
    assert "fetch(" not in js
    assert "XMLHttpRequest" not in js
    assert "innerHTML" not in js
