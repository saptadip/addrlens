"""Inference-service selfcheck. Run: `python -m inference.selfcheck`.

Two phases:
  1. Template selfchecks (pure, prompt-shape asserts).
  2. Live backend load + one generation per template. Backend picked by
     INFERENCE_BACKEND env-var — must be `mlx` on dev, `llama` on prod.

Exit criterion (plan §7.8): the anti-inversion asserts on the impression
prompt must pass under BOTH backends before Ship D prod cutover.
"""
from __future__ import annotations

import os
import subprocess
import sys

TEMPLATE_MODULES = ["inference.templates.impression", "inference.templates.explain"]


def run_pure() -> None:
    for mod in TEMPLATE_MODULES:
        print(f"→ {mod} …", end=" ", flush=True)
        r = subprocess.run([sys.executable, "-m", mod], capture_output=True, text=True)
        if r.returncode != 0:
            print("FAIL"); print(r.stdout, r.stderr); sys.exit(1)
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "OK")


def run_live() -> None:
    """Load the configured backend and generate one impression + one explain.
    Anti-inversion is verified on the negative-mode generation."""
    from inference.templates import explain as explain_tpl
    from inference.templates import impression as impression_tpl

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

    # -- impression: negative mode, anti-inversion check ---------------------
    print("→ impression / negative …", flush=True)
    summary = impression_tpl.run(backend, {
        "address": "Kastanienallee 12, 10435",
        "votes": {
            "amenities": {
                "happy": [],
                "sad": ["Supermarkets"],
                "sad_details": {"Supermarkets": "no Rewe nearby"},
            }
        },
    })
    text = (summary.get("amenities") or "").lower()
    print(f"  → {summary['amenities']!r}")
    # Anti-inversion: user said "no Rewe nearby"; model must NOT invert to
    # "one Rewe nearby" / "Rewe is close" / similar positive spin.
    assert "no rewe" in text or "no supermarket" in text or "no " in text, \
        "negative-mode output should preserve the user's negation"
    assert not any(bad in text for bad in ["rewe is close", "rewe nearby is", "one rewe"]), \
        f"anti-inversion regression detected — text spun a complaint into a positive: {summary['amenities']!r}"

    # -- explain: sentiment-neutral generation on a synthetic Kita ----------
    print("→ explain / kita …", flush=True)
    got = explain_tpl.run(backend, {
        "card_type": "edu-kita",
        "fields": {"name": "Kita Sonnenschein", "t_art": "freier Träger",
                   "ang_1": "Situationsansatz", "e_platz": "65"},
    })
    print(f"  → {got['explanation']!r}")
    assert "explanation" in got
    assert len(got["explanation"]) > 20, "explanation should be non-trivial"

    print("→ live selfcheck OK")


def main() -> None:
    print("=== template selfchecks (pure) ===")
    run_pure()
    print("\n=== live backend selfcheck ===")
    run_live()
    print("\ninference selfcheck: OK")


if __name__ == "__main__":
    main()
