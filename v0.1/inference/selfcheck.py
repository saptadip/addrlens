"""Inference-service selfcheck. Run: `python -m inference.selfcheck`.

Two phases:
  1. Template selfchecks (pure, prompt-shape asserts). Anti-inversion
     coverage lives inside each per-lens template's `__main__` block
     (rollup + highlight-tone filter + section-vs-tile disambiguation).
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
    "inference.templates.lens_young_family_insight",
    "inference.templates.lens_newcomer_insight",
    "inference.templates.lens_quiet_living_insight",
    "inference.templates.lens_commuter_insight",
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
    end-to-end for at least one template.

    Skipped when INFERENCE_LOCAL_BACKEND=off (prod Cloudflare-only
    mode) — no local model is loaded in that config, so a live test
    that spins one up would defeat the purpose."""
    from inference.templates import history as history_tpl

    local_enabled = os.environ.get(
        "INFERENCE_LOCAL_BACKEND", "on").strip().lower() not in ("0", "false", "no", "off")
    if not local_enabled:
        print("→ skipping live phase (INFERENCE_LOCAL_BACKEND=off)", flush=True)
        return

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
