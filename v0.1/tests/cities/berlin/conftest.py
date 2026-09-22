"""Directory-level marker propagation for Berlin tests. See
tests/cities/hamburg/conftest.py for rationale."""
import pathlib

import pytest


def pytest_collection_modifyitems(config, items):
    berlin = pytest.mark.berlin
    this_dir = pathlib.Path(__file__).parent.resolve()
    for item in items:
        try:
            item_path = pathlib.Path(str(item.fspath)).resolve()
        except (TypeError, ValueError):
            continue
        if this_dir in item_path.parents or item_path == this_dir:
            item.add_marker(berlin)
