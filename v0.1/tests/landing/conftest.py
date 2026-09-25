"""Shared fixtures for landing container tests.

Landing container reads web/landing/index.html at module import time
via app.landing.main._load_index(). CI checkouts (and this fixture)
provide a minimal web/landing/ tree so import succeeds.
"""
from pathlib import Path

import pytest

# Repo root = 3 levels above this file (v0.1/tests/landing/conftest.py).
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WEB_LANDING = REPO_ROOT / "web" / "landing"


@pytest.fixture
def ensure_landing_index(monkeypatch):
    """Ensure web/landing/index.html + static/ exist for module import.

    If the real files already exist (later tasks), yield without touching
    them. Otherwise write a minimal placeholder that _load_index() can
    read. Restore state via monkeypatch's automatic cleanup where possible;
    files created here are removed at fixture teardown.
    """
    created_files: list[Path] = []
    if not WEB_LANDING.exists():
        WEB_LANDING.mkdir(parents=True)
        created_files.append(WEB_LANDING)
    if not (WEB_LANDING / "index.html").exists():
        (WEB_LANDING / "index.html").write_text(
            "<!doctype html><html><body><!-- UMAMI-INJECT --></body></html>",
            encoding="utf-8",
        )
        created_files.append(WEB_LANDING / "index.html")
    if not (WEB_LANDING / "static").exists():
        (WEB_LANDING / "static").mkdir()
        created_files.append(WEB_LANDING / "static")
    yield WEB_LANDING
    # Teardown: only remove files this fixture created (idempotent).
    for p in reversed(created_files):
        if p.is_file():
            p.unlink()
        elif p.is_dir() and not any(p.iterdir()):
            p.rmdir()
