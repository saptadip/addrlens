"""Directory-level marker propagation for Hamburg tests.

pytest's module-level `pytestmark = pytest.mark.hamburg` does NOT
propagate from a conftest to sibling test modules (conftest is not a
test module, so its module-level marks are ignored). The
`pytest_collection_modifyitems` hook is the standard pattern: add the
marker to every item collected under this directory. New test files
dropped in here are auto-marked without touching the file."""
import pathlib

import pytest


def pytest_collection_modifyitems(config, items):
    hamburg = pytest.mark.hamburg
    this_dir = pathlib.Path(__file__).parent.resolve()
    for item in items:
        try:
            item_path = pathlib.Path(str(item.fspath)).resolve()
        except (TypeError, ValueError):
            continue
        # `.is_relative_to` is 3.9+; matches every item whose file lives
        # under this conftest's directory (recursively). String matching
        # on "tests/cities/hamburg/" would false-positive on any repo
        # that happens to contain that substring in an unrelated path.
        if this_dir in item_path.parents or item_path == this_dir:
            item.add_marker(hamburg)
