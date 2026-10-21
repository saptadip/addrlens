"""Import-guard: landing must stay minimal.

Whitelist (not blacklist) so future edits reaching for app.config /
app.deps / any new app.<x> are caught. Only `app`, `app.landing`, and
`app.landing.main` are allowed under the app namespace.
"""
import importlib
import sys

_ALLOWED_APP_MODULES = {"app", "app.landing", "app.landing.main"}


def test_landing_imports_only_whitelisted_app_modules(ensure_landing_index):
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]

    importlib.import_module("app.landing.main")

    imported = {m for m in sys.modules if m == "app" or m.startswith("app.")}
    unexpected = imported - _ALLOWED_APP_MODULES
    assert not unexpected, (
        f"app.landing must stay minimal. Unexpected app.* imports: "
        f"{sorted(unexpected)}. Landing exists to be snappy — do not "
        "reach for app.core / app.cities / app.config / app.deps / "
        "app.routes here."
    )
