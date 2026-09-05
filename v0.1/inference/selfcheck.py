"""Inference-service selfcheck. Run: `python -m inference.selfcheck`.

Two phases:
  1. Template selfchecks (pure, prompt-shape asserts). Anti-inversion
     coverage that used to live in the removed `impression` template
     now lives per-tile in each `*_insight.py` template's `__main__`
     block, and at the lens level in `lens_newcomer_insight.py` (rollup
     + highlight-tone filter). Run those modules directly to exercise
     the inversion guards.
  2. Live backend load + one generation on the `history` template.
     Backend picked by INFERENCE_BACKEND env-var — must be `mlx` on
     dev, `llama` on prod.
"""
from __future__ import annotations

import os
import subprocess
import sys

TEMPLATE_MODULES = [
    "inference.templates.history",
    # Shared scaffolding for 16 tier+features insight templates. Pinned
    # here so a future edit to build_tier_messages / run_tier is caught
    # before the tile-specific selfchecks run and mask the drift.
    "inference.templates._insight_base",
    "inference.templates.lens_newcomer_insight",
]

# Pure `__main__` blocks that exercise the inference service's async /
# timeout / lifespan guarantees without loading a model. Run alongside
# the template selfchecks so a future refactor of `main.py` can't
# silently regress the /summarize stability contract.
STABILITY_MODULES = ["inference.stability_selfcheck"]


def run_pure() -> None:
    for mod in TEMPLATE_MODULES + STABILITY_MODULES:
        print(f"→ {mod} …", end=" ", flush=True)
        r = subprocess.run([sys.executable, "-m", mod], capture_output=True, text=True)
        if r.returncode != 0:
            print("FAIL"); print(r.stdout, r.stderr); sys.exit(1)
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "OK")


def run_live() -> None:
    """Load the configured backend and generate one `history` paragraph.
    Confirms the local model warms + the /summarize round-trip works
    end-to-end for at least one template."""
    from inference.templates import history as history_tpl

    backend_name = os.environ.get("INFERENCE_BACKEND", "mlx")
    print(f"→ loading backend={backend_name} …", flush=True)
    if backend_name == "mlx":
        from inference.runtime.mlx_backend import MlxBackend
        backend = MlxBackend()
    elif backend_name == "llama":
        from inference.runtime.llama_backend import LlamaBackend
        backend = LlamaBackend()
    else:
        raise SystemExit(f"unknown INFERENCE_BACKEND={backend_name!r}")
    print(f"  model={backend.model_id}")

    print("→ history / synthetic Stolperstein …", flush=True)
    got = history_tpl.run(backend, {
        "bezirk":   "Pankow",
        "ortsteil": "Prenzlauer Berg",
        "features": [
            {"distance_m": 40, "historic": "memorial", "name": "Anna Winter",
             "inscription": "Hier wohnte Anna Winter, Jg. 1889, deportiert 1942"},
        ],
    })
    print(f"  → {got['history']!r}")
    assert "history" in got
    assert len(got["history"]) > 20, "history should be non-trivial"

    print("→ live selfcheck OK")


def main() -> None:
    print("=== template selfchecks (pure) ===")
    run_pure()
    print("\n=== live backend selfcheck ===")
    run_live()
    print("\ninference selfcheck: OK")


if __name__ == "__main__":
    main()
