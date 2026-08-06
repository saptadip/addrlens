"""Backend interface. Two backends implement this:

* mlx_backend.MlxBackend    — Apple Silicon dev
* llama_backend.LlamaBackend — Linux prod (llama-cpp-python + GGUF)

Templates + sampler settings live above this line (see inference.templates)
so switching backends changes nothing about the prompt logic.
"""
from __future__ import annotations

from typing import Protocol


class Backend(Protocol):
    """Chat-template generation. Both backends load a model at construction
    time; `generate_from_messages` is called per-request under the shared
    caller-side lock (models are not thread-safe)."""

    model_id: str

    def generate_from_messages(
        self,
        msgs: list[dict],
        max_tokens: int,
        temp: float,
        top_p: float,
        repetition_penalty: float,
    ) -> str:
        """Apply the chat template + generate. Returns the raw generated text
        (leading assistant preamble stripped)."""
        ...
