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
def ensure_landing_index():
    """Ensure web/landing/index.html + static/ exist for module import.

    Snapshot-and-restore: capture the WEB_LANDING file tree on entry
    (after ensuring stubs), diff on exit, and remove anything that
    appeared during the test. This cleans up both fixture-created
    stubs AND files written by test bodies (route tests write
    robots.txt, sitemap.xml, impressum.html, datenschutzerklaerung.html
    into the real path during their assertion setup — those writes
    would otherwise persist and get slurped by `git add`).

    Real files created by prior tasks (Task 3's index.html,
    landing.css, static/img/*, static/fonts/*, README.md) are
    captured in the pre-yield snapshot and survive teardown.
    """
    web_landing_created = False
    if not WEB_LANDING.exists():
        WEB_LANDING.mkdir(parents=True)
        web_landing_created = True

    # Create minimal stubs only if missing (idempotent).
    if not (WEB_LANDING / "index.html").exists():
        (WEB_LANDING / "index.html").write_text(
            "<!doctype html><html><body><!-- UMAMI-INJECT --></body></html>",
            encoding="utf-8",
        )
    if not (WEB_LANDING / "static").exists():
        (WEB_LANDING / "static").mkdir()

    # Snapshot AFTER setup: stubs are in "before", only test-body writes are in "after - before".
    snapshot = set()
    if WEB_LANDING.exists():
        snapshot = set(WEB_LANDING.rglob("*"))

    yield WEB_LANDING

    # Teardown: remove anything created since snapshot (test-body writes).
    if not WEB_LANDING.exists():
        return
    after = set(WEB_LANDING.rglob("*"))
    new_items = after - snapshot
    for p in sorted(new_items, key=lambda x: len(x.parts), reverse=True):
        try:
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
        except OSError:
            pass

    # If we created WEB_LANDING itself and it's now empty, remove it.
    if web_landing_created and not any(WEB_LANDING.iterdir()):
        WEB_LANDING.rmdir()
