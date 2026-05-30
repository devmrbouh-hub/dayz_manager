"""Tests for static file serving in src.main."""

from __future__ import annotations

from pathlib import Path

from src import main


def _set_web_root(monkeypatch, web_dir: Path):
    monkeypatch.setattr(main, "web_dir", web_dir)
    monkeypatch.setattr(main, "web_root", web_dir.resolve())


def test_resolve_static_path_returns_file_within_web_dir(tmp_path, monkeypatch):
    web_dir = tmp_path / "web"
    asset = web_dir / "js" / "app.js"
    asset.parent.mkdir(parents=True)
    asset.write_text("console.log('ok');", encoding="utf-8")
    _set_web_root(monkeypatch, web_dir)

    resolved = main.resolve_static_path("js/app.js")

    assert resolved == asset.resolve()


def test_resolve_static_path_blocks_parent_traversal(tmp_path, monkeypatch):
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    secret = tmp_path / "config.json"
    secret.write_text('{"secret": true}', encoding="utf-8")
    _set_web_root(monkeypatch, web_dir)

    resolved = main.resolve_static_path("../config.json")

    assert resolved is None


def test_serve_static_falls_back_to_index_for_parent_traversal(tmp_path, monkeypatch, event_loop):
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    index = web_dir / "index.html"
    index.write_text("<html>ui</html>", encoding="utf-8")
    (tmp_path / "config.json").write_text('{"secret": true}', encoding="utf-8")
    _set_web_root(monkeypatch, web_dir)

    response = event_loop.run_until_complete(main.serve_static("../config.json"))

    assert response.path == str(index)
