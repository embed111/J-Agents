from __future__ import annotations

from pathlib import Path

def load_index_page_html() -> str:
    path = Path(__file__).resolve().parent / "templates" / "index.html"
    return path.read_text(encoding="utf-8")


def load_index_page_css() -> str:
    path = Path(__file__).resolve().parent / "templates" / "index.css"
    return path.read_text(encoding="utf-8")


HTML_PAGE = load_index_page_html()
CSS_PAGE = load_index_page_css()
