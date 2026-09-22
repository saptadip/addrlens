"""Mirror of tests/cities/hamburg/test_hook_applies_marker.py — proves
the Berlin conftest's `pytest_collection_modifyitems` hook applies
`@pytest.mark.berlin` to every item under this directory."""


def test_this_file_is_auto_marked_berlin(request):
    marks = {m.name for m in request.node.iter_markers()}
    assert "berlin" in marks, f"expected berlin marker; got {marks}"
