"""Linux prod backend (llama-cpp-python + GGUF). Plan §7.1.1.

Model file `Qwen2.5-1.5B-Instruct-Q4_K_M.gguf` (~1.0 GB) is baked into the
prod inference Docker image (ops/Dockerfile.inference). Location is picked
by env-var LLAMA_MODEL_PATH; default matches the Dockerfile COPY target.

ponytail: llama-cpp-python's Llama class holds its own state and is NOT
thread-safe — callers (main.py) must serialize with a lock. Same story as
phase3's MLX handling.
"""
from __future__ import annotations

import os

DEFAULT_MODEL_ID   = "Qwen2.5-1.5B-Instruct-Q4_K_M"
DEFAULT_MODEL_PATH = "/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf"


class LlamaBackend:
    def __init__(self, model_path: str | None = None, n_ctx: int = 4096):
        # Lazy import — llama-cpp-python is only installed in prod image.
        from llama_cpp import Llama
        path = model_path or os.environ.get("LLAMA_MODEL_PATH", DEFAULT_MODEL_PATH)
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"GGUF model not found at {path}. Set LLAMA_MODEL_PATH or bake "
                f"the file into the inference image (ops/Dockerfile.inference).")
        # verbose=False so Llama's per-request tracing doesn't spam prod logs.
        self.llm = Llama(model_path=path, n_ctx=n_ctx, verbose=False, chat_format="chatml")
        self.model_id = DEFAULT_MODEL_ID

    def generate_from_messages(
        self,
        msgs: list[dict],
        max_tokens: int,
        temp: float,
        top_p: float,
        repetition_penalty: float,
    ) -> str:
        # create_chat_completion applies llama-cpp's chat template internally.
        # The Qwen2.5 model expects ChatML — passed via chat_format at load.
        r = self.llm.create_chat_completion(
            messages=msgs,
            max_tokens=max_tokens,
            temperature=temp,
            top_p=top_p,
            repeat_penalty=repetition_penalty,
        )
        return r["choices"][0]["message"]["content"].strip()
