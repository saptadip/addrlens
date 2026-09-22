"""Regression test: the directory-level conftest hook must apply
`@pytest.mark.hamburg` to every test collected under this directory.
Silent-failure guard for the "conftest pytestmark doesn't propagate"
bug that would otherwise make `pytest -m hamburg` collect zero tests."""


def test_this_file_is_auto_marked_hamburg(request):
    marks = {m.name for m in request.node.iter_markers()}
    assert "hamburg" in marks, f"expected hamburg marker; got {marks}"
