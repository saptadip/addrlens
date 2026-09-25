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

    Snapshot-and-restore of file *content* (not just paths). Route tests
    write stubs into real file paths (robots.txt, sitemap.xml, impressum,
    datenschutzerklaerung) — those writes clobber real Task 4 content
    unless we restore original bytes at teardown. Paths-only snapshots
    couldn't distinguish "same path, corrupted content" from "same path,
    unchanged".
    """
    web_landing_created = False
    if not WEB_LANDING.exists():
        WEB_LANDING.mkdir(parents=True)
        web_landing_created = True

    # Idempotent stub creation for imports.
    if not (WEB_LANDING / "index.html").exists():
        (WEB_LANDING / "index.html").write_text(
            "<!doctype html><html><body><!-- UMAMI-INJECT --></body></html>",
            encoding="utf-8",
        )
    if not (WEB_LANDING / "static").exists():
        (WEB_LANDING / "static").mkdir()

    # Snapshot bytes for every regular file under WEB_LANDING. Directories
    # are tracked separately so we can prune ones created by tests.
    snapshot_files: dict[Path, bytes] = {}
    snapshot_dirs: set[Path] = set()
    for p in WEB_LANDING.rglob("*"):
        if p.is_file():
            snapshot_files[p] = p.read_bytes()
        elif p.is_dir():
            snapshot_dirs.add(p)

    yield WEB_LANDING

    # Teardown.
    if not WEB_LANDING.exists():
        return

    # (1+2) Restore snapshot files.
    for p, original in snapshot_files.items():
        try:
            if not p.exists() or p.read_bytes() != original:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(original)
        except OSError:
            pass

    # (3) Remove files that appeared during the test.
    for p in WEB_LANDING.rglob("*"):
        if p.is_file() and p not in snapshot_files:
            try:
                p.unlink()
            except OSError:
                pass

    # (4) Prune directories not in snapshot, deepest-first.
    current_dirs = [p for p in WEB_LANDING.rglob("*") if p.is_dir()]
    for p in sorted(current_dirs, key=lambda x: len(x.parts), reverse=True):
        if p not in snapshot_dirs:
            try:
                p.rmdir()
            except OSError:
                pass  # not empty — fine

    # (5) If we created WEB_LANDING itself and it's empty, remove it.
    if web_landing_created and WEB_LANDING.exists() and not any(WEB_LANDING.iterdir()):
        WEB_LANDING.rmdir()
